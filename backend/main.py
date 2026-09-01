"""
SatQuery AI — FastAPI Application
Main entry point with all API routes.
"""

import json
import asyncio
import base64
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from backend.schemas.models import DemoRunRequest, AnalyzeRequest, DemoScenario, TaskType
from backend.services.analysis_service import (
    run_analysis, get_session, get_demo_scenarios, DEMO_SCENARIOS
)
from backend.tools import demo_imagery
from backend.tools.scene_loader import UploadedSceneLoader
from backend.providers.provider_factory import get_provider_status


# ─── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SatQuery AI",
    description="Interactive Vision-Language Agent for Multimodal Remote Sensing Analysis",
    version="1.1.0-credibility",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    provider_status = get_provider_status()
    return {
        "status": "ok",
        "version": "1.1.0-credibility",
        "mode": "demo+real",
        "real_algorithms": [
            "rgb_cloud_detector_v1",
            "abs_diff_otsu_v1",
            "ECC_registration",
            "opencv_telea_inpaint",
            "evidence_strength_calculator_v1",
        ],
        "providers": provider_status,
        "bhoonidhi": _bhoonidhi_status(),
    }


def _bhoonidhi_status() -> dict:
    try:
        from backend.api.bhoonidhi_client import get_bhoonidhi_client
        client = get_bhoonidhi_client()
        return {
            "configured": client.is_configured(),
            "note": (
                "Ready" if client.is_configured()
                else "Set BHOONIDHI_USER + BHOONIDHI_PASSWORD to enable."
            ),
        }
    except Exception:
        return {"configured": False, "note": "Bhoonidhi connector unavailable."}


# ─── Demo Scenarios ───────────────────────────────────────────────────────────

@app.get("/api/demo/scenarios")
async def list_scenarios():
    scenarios = []
    for sid, s in DEMO_SCENARIOS.items():
        scenarios.append({
            "scenario_id": sid,
            "title": s["title"],
            "description": s["description"],
            "default_query": s["default_query"],
            "task_type": s["task_type"].value,
            "tags": s["tags"],
            "images": [img.model_dump() for img in s["images"]],
        })
    return {"scenarios": scenarios}


# ─── Analyze (SSE Streaming) ──────────────────────────────────────────────────

class AnalyzePayload(BaseModel):
    query: str
    demo_scenario: Optional[str] = None
    image_ids: list = []
    uploaded_images: List[str] = []   # base64 PNG strings from real uploads


async def _sse_generator(payload: AnalyzePayload):
    """Stream tool trace events as Server-Sent Events."""
    async for event in run_analysis(
        query=payload.query,
        demo_scenario=payload.demo_scenario,
        image_ids=payload.image_ids,
        uploaded_images=payload.uploaded_images if payload.uploaded_images else None,
    ):
        data = json.dumps(event)
        yield f"data: {data}\n\n"
        await asyncio.sleep(0)


_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


@app.post("/api/analyze")
async def analyze(payload: AnalyzePayload):
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    return StreamingResponse(
        _sse_generator(payload),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@app.post("/api/demo/run")
async def run_demo(payload: DemoRunRequest):
    """Run a preloaded demo scenario."""
    if payload.scenario_id not in DEMO_SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail=f"Demo scenario '{payload.scenario_id}' not found.",
        )
    scenario = DEMO_SCENARIOS[payload.scenario_id]
    query = payload.query or scenario["default_query"]
    analyze_payload = AnalyzePayload(query=query, demo_scenario=payload.scenario_id)
    return StreamingResponse(
        _sse_generator(analyze_payload),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


# ─── Session Retrieval ────────────────────────────────────────────────────────

@app.get("/api/analysis/{analysis_id}")
async def get_analysis(analysis_id: str):
    session = get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis session not found.")
    return session.model_dump()


@app.get("/api/analysis/{analysis_id}/trace")
async def get_trace(analysis_id: str):
    session = get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis session not found.")
    return {"trace": [t.model_dump() for t in session.trace]}


@app.get("/api/analysis/{analysis_id}/results")
async def get_results(analysis_id: str):
    session = get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis session not found.")
    return {
        "analysis_id": session.analysis_id,
        "final_answer": session.final_answer,
        "confidence": session.confidence,
        "evidence_status": session.evidence_status.value,
        "evidence_points": session.evidence_points,
        "visual_outputs": session.visual_outputs,
    }


# ─── Real Image Upload ────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    """
    Upload a satellite image for real analysis.

    Returns:
      - image_id: unique identifier
      - image_b64: base64 PNG (for use in /api/analyze uploaded_images field)
      - width, height, n_channels: real image dimensions
      - sensor_hint: guessed from filename (not verified from metadata)
      - provenance: "USER_UPLOAD"
      - warnings: any issues found during loading

    The image is NOT stored permanently — it lives in the response only.
    Pass image_b64 in the uploaded_images list of /api/analyze to run real algorithms.
    """
    content_type = file.content_type or ""
    allowed = ("image/png", "image/jpeg", "image/jpg", "image/tiff")
    if not any(ct in content_type for ct in ("png", "jpeg", "jpg", "tiff")):
        # Also allow by filename extension
        fname = (file.filename or "").lower()
        if not any(fname.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff")):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file type '{content_type}'. "
                    f"Upload PNG, JPEG, or GeoTIFF."
                ),
            )

    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {exc}")

    # Validate and load via UploadedSceneLoader
    loader = UploadedSceneLoader()
    try:
        scene = loader.load(file_bytes, filename=file.filename or "upload")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    import uuid
    image_id = str(uuid.uuid4())

    # Guess sensor from filename (purely informational — never used for band assignment)
    fname_lower = (file.filename or "").lower()
    sensor_hint = "Unknown"
    if "sentinel" in fname_lower:
        sensor_hint = "Sentinel (detected from filename only)"
    elif "liss" in fname_lower:
        sensor_hint = "LISS-IV candidate (unverified — no metadata parsed)"
    elif "landsat" in fname_lower:
        sensor_hint = "Landsat (detected from filename only)"

    return {
        "image_id": image_id,
        "filename": file.filename,
        "image_b64": scene.image_b64,
        "width": scene.width,
        "height": scene.height,
        "n_channels": scene.n_channels,
        "provenance": "USER_UPLOAD",
        "sensor_hint": sensor_hint,
        "band_semantics": [],   # always empty for uploads — unknown
        "warnings": scene.warnings,
        "status": "ready",
        "note": (
            "Pass image_b64 in the uploaded_images field of /api/analyze "
            "to run real CPU algorithms on this image."
        ),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
