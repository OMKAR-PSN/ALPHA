"""
SatQuery AI — Analysis Service
Orchestrates the full analysis pipeline: controller → tools → evidence → synthesis.

Key upgrades from prototype:
  - Hardcoded confidence overrides removed; evidence.py drives all scores.
  - LOW_EVIDENCE SSE event emitted when evidence_strength < threshold.
  - Secondary evidence check: returns NO_SECONDARY_EVIDENCE_AVAILABLE honestly.
  - Uploaded images passed to tools via context["uploaded_images"].
  - Provenance fields (execution_mode, algorithm) forwarded through SSE.
  - UNRELIABLE_REGISTRATION results excluded from evidence scoring.
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from backend.schemas.models import (
    AnalysisSession, AnalysisInput, ImageMetadata, TaskType,
    TraceStep, ToolResult, ToolStatus, EvidenceStatus, ConfidenceLevel,
    ControllerPlan,
)
from backend.schemas.provenance import (
    ExecutionMode, InputProvenance, SecondaryEvidenceStatus
)
from backend.controller.central_controller import CentralController
from backend.solution_space.strategy_registry import (
    get_strategy, maybe_insert_cloud_reconstruction
)
from backend.tools.specialist_tools import get_tool, TOOL_REGISTRY
from backend.tools import demo_imagery
from backend.tools.scene_loader import load_scene, LoadedScene


# In-memory session store (replace with DB in production)
SESSION_STORE: Dict[str, AnalysisSession] = {}

controller = CentralController()


# ─── Demo Scenario Data ───────────────────────────────────────────────────────

DEMO_SCENARIOS = {
    "demo1": {
        "title": "Real Change Scene",
        "description": "Bi-temporal registered change analysis (Sentinel-2 L2A).",
        "default_query": "Did the flood area expand near the river?",
        "task_type": TaskType.BI_TEMPORAL_CHANGE,
        "tags": ["REAL SATELLITE", "change detection", "bi-temporal", "flood"],
        "images": [
            ImageMetadata(sensor="Sentinel-2", acquisition_date="21 Apr 2022", image_type="Optical",
                         resolution_m=10.0, cloud_coverage_pct=9.0, cloud_status="Clear",
                         processing_status="Ready", filename="pre_flood.tif"),
            ImageMetadata(sensor="Sentinel-2", acquisition_date="15 Jul 2022", image_type="Optical",
                         resolution_m=10.0, cloud_coverage_pct=48.0, cloud_status="Detected",
                         processing_status="Ready", filename="peak_flood.tif"),
        ],
    },
    "demo3": {
        "title": "Real Cloud Scene",
        "description": "Optical cloud-quality analysis (Sentinel-2 L2A).",
        "default_query": "Detect clouds and reconstruct the hazy areas.",
        "task_type": TaskType.CLOUD_ANALYSIS,
        "tags": ["REAL SATELLITE", "cloud reconstruction", "automated"],
        "images": [
            ImageMetadata(sensor="Sentinel-2", acquisition_date="15 Jul 2022", image_type="Optical",
                         resolution_m=10.0, cloud_coverage_pct=35.0, cloud_status="Detected",
                         processing_status="Reconstruction required", filename="cloudy_scene.tif"),
        ],
    },
    "demo2": {
        "title": "SAR + Optical",
        "description": "Cross-modal reasoning. (EXPERIMENTAL / DATA PENDING)",
        "default_query": "Compare the optical and SAR images and identify built-up areas.",
        "task_type": TaskType.SAR_OPTICAL,
        "tags": ["EXPERIMENTAL", "SAR", "optical", "fusion"],
        "images": [
            ImageMetadata(sensor="Sentinel-2", acquisition_date="18 Oct 2025", image_type="Optical",
                         resolution_m=10.0, cloud_coverage_pct=5.0, cloud_status="Clear",
                         processing_status="Ready", filename="optical_scene.tif"),
            ImageMetadata(sensor="Sentinel-1", acquisition_date="19 Oct 2025", image_type="SAR",
                         resolution_m=10.0, cloud_coverage_pct=0.0, cloud_status="N/A (SAR)",
                         processing_status="Ready", filename="sar_scene.tif"),
        ],
    },
}


def get_demo_scenarios():
    return DEMO_SCENARIOS


def _compute_confidence_level(conf: float) -> ConfidenceLevel:
    if conf >= 0.75:
        return ConfidenceLevel.HIGH
    elif conf >= 0.50:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _build_context(
    session: AnalysisSession,
    tool_results_so_far: List[ToolResult],
    uploaded_images: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "query": session.query,
        "tool_results": [r.model_dump() for r in tool_results_so_far],
        "confidence_threshold": controller.CONFIDENCE_THRESHOLD,
        "images": [],
        "uploaded_images": uploaded_images or [],
    }


def _tool_done_event(step_i: int, tool_name: str, step_desc: Dict, result: ToolResult) -> Dict:
    """Build the tool_done SSE event dict including provenance fields."""
    return {
        "type": "tool_done",
        "step_index": step_i,
        "tool_name": tool_name,
        "step_name": step_desc.get("step_name", tool_name),
        "status": result.status.value,
        "confidence": result.confidence,
        "message": result.message,
        "result": result.result,
        "visual_output": result.visual_output,
        "visual_type": result.visual_type,
        "metadata": result.metadata,
        "execution_time_ms": result.execution_time_ms,
        "is_auto_inserted": step_desc.get("is_auto_inserted", False),
        # Provenance fields for frontend badge
        "execution_mode": result.execution_mode.value if result.execution_mode else None,
        "input_provenance": result.input_provenance.value if result.input_provenance else None,
        "algorithm": result.algorithm,
        "evidence_excludable": result.evidence_excludable,
        "warnings": result.warnings,
        "registration_quality": result.registration_quality.value if result.registration_quality else None,
    }


async def run_analysis(
    query: str,
    demo_scenario: Optional[str] = None,
    image_ids: Optional[List[str]] = None,
    uploaded_images: Optional[List[str]] = None,  # list of base64 strings
) -> AsyncGenerator[Dict, None]:
    """
    Main analysis pipeline — async generator yielding SSE trace events.

    uploaded_images: base64 PNG strings from real user uploads.
                     When present, real CPU algorithms run on actual pixels.
                     When absent, demo/synthetic fallbacks are used.
    """
    session_id = str(uuid.uuid4())

    # ── Resolve scenario ──────────────────────────────────────────────────────
    scenario = DEMO_SCENARIOS.get(demo_scenario, DEMO_SCENARIOS["demo1"]) if demo_scenario else DEMO_SCENARIOS["demo1"]
    actual_scenario_key = demo_scenario or "demo1"
    images_meta = scenario["images"]
    has_real_images = bool(uploaded_images)

    # ── Create session ────────────────────────────────────────────────────────
    session = AnalysisSession(
        analysis_id=session_id,
        query=query,
        inputs=[
            AnalysisInput(role=f"image_{i}", image_id=str(uuid.uuid4()), metadata=m)
            for i, m in enumerate(images_meta)
        ],
        is_demo=not has_real_images,
        status="running",
    )

    # ── Step 0: Controller interprets query ───────────────────────────────────
    yield {"type": "session_created", "analysis_id": session_id}
    yield {"type": "step", "step": "query_understanding", "status": "running",
           "message": "Controller analysing query…"}
    await asyncio.sleep(0.4)

    plan: ControllerPlan = controller.interpret_query(query, image_count=len(images_meta))
    session.task_type = plan.task_type
    session.intent = plan.intent

    yield {
        "type": "step", "step": "query_understanding", "status": "done",
        "message": plan.intent,
        "detail": {
            "task_type": plan.task_type.value,
            "target": plan.target,
            "spatial_reference": plan.spatial_reference,
            "dates": plan.dates,
            "requires_sar": plan.requires_sar,
            "reasoning": plan.reasoning,
        },
    }

    if actual_scenario_key == "demo3":
        plan.task_type = TaskType.BI_TEMPORAL_CHANGE

    # ── Step 1: Strategy selection ────────────────────────────────────────────
    yield {"type": "step", "step": "strategy_selection", "status": "running",
           "message": "Selecting analysis pipeline…"}
    await asyncio.sleep(0.3)

    tool_plan = get_strategy(plan.task_type)
    step_descriptions = controller.generate_step_descriptions(tool_plan)

    yield {
        "type": "step", "step": "strategy_selection", "status": "done",
        "message": f"{plan.task_type.value.replace('_', ' ').title()} pipeline selected.",
        "detail": {"tools": tool_plan, "steps": step_descriptions},
    }

    session.plan = tool_plan

    # ── Thumbnails ────────────────────────────────────────────────────────────
    thumbnails = []
    loaded_scenes = []
    
    if uploaded_images and len(uploaded_images) >= 2:
        thumbnails = uploaded_images[:2]   # Use real uploaded images as thumbnails
    elif actual_scenario_key:
        try:
            loaded_scenes = load_scene(actual_scenario_key)
            if loaded_scenes:
                thumbnails = [s.image_b64 for s in loaded_scenes]
                # Populate uploaded_images so legacy pipeline still sees bytes
                if not uploaded_images:
                    uploaded_images = thumbnails
        except Exception as e:
            print(f"Error loading scene {actual_scenario_key}: {e}")
            # Fallback to demo_imagery if registry fails
            if actual_scenario_key == "demo1":
                thumbnails = [
                    demo_imagery.generate_urban_scene("2024", expansion_factor=0.0),
                    demo_imagery.generate_urban_scene("2026", expansion_factor=0.6),
                ]
            elif actual_scenario_key == "demo2":
                thumbnails = [
                    demo_imagery.generate_urban_scene("2025", expansion_factor=0.3),
                    demo_imagery.generate_sar_image(),
                ]
            elif actual_scenario_key == "demo3":
                thumbnails = [
                    demo_imagery.generate_urban_scene("2026-Jan", expansion_factor=0.1),
                    demo_imagery.generate_cloud_image(),
                ]

    yield {"type": "thumbnails", "thumbnails": thumbnails}

    # ── Execute tools ─────────────────────────────────────────────────────────
    tool_results_accumulated: List[ToolResult] = []
    current_plan = list(tool_plan)
    cloud_reconstruction_auto_inserted = False
    cloud_mask_b64_from_detection: Optional[str] = None

    for step_i, tool_name in enumerate(current_plan):
        step_desc = next(
            (s for s in step_descriptions if s["tool_name"] == tool_name),
            {"step_name": tool_name, "description": "", "is_auto_inserted": False},
        )

        yield {
            "type": "tool_start",
            "step_index": step_i,
            "tool_name": tool_name,
            "step_name": step_desc.get("step_name", tool_name),
            "description": step_desc.get("description", ""),
            "is_auto_inserted": step_desc.get("is_auto_inserted", False) or (
                tool_name == "cloud_reconstruction" and cloud_reconstruction_auto_inserted
            ),
        }

        await asyncio.sleep(
            0.8 if tool_name in ("cloud_reconstruction", "bi_temporal_change_detection") else 0.4
        )

        context = _build_context(session, tool_results_accumulated, uploaded_images)
        context["demo_scenario"] = actual_scenario_key
        context["target"] = plan.target
        context["scene_id"] = actual_scenario_key if not has_real_images else None

        # Pass cloud mask from detection step to reconstruction step
        if tool_name == "cloud_reconstruction" and cloud_mask_b64_from_detection:
            context["cloud_mask_b64"] = cloud_mask_b64_from_detection

        # Build inputs: real images go into "images" list
        tool_inputs: Dict[str, Any] = {
            "images": uploaded_images or [],
            "loaded_scenes": loaded_scenes,
            "metadata": [],
            "params": {},
            "context": context,
        }

        try:
            tool = get_tool(tool_name)
            result = tool.timed_run(tool_inputs)
        except Exception as e:
            result = ToolResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                confidence=0.0,
                result={},
                message=f"Tool error: {str(e)}",
                is_demo=True,
                execution_mode=ExecutionMode.SIMULATED,
                input_provenance=InputProvenance.UNKNOWN,
            )

        # Capture cloud mask for reconstruction step
        if tool_name == "cloud_detection":
            mask = result.metadata.get("mask_b64") or result.result.get("cloud_mask_b64")
            if mask:
                cloud_mask_b64_from_detection = mask

        tool_results_accumulated.append(result)
        session.tool_results.append(result)

        yield _tool_done_event(step_i, tool_name, step_desc, result)

        # ── Dynamic cloud reconstruction insertion ────────────────────────────
        if tool_name == "cloud_detection" and result.result.get("requires_reconstruction", False):
            updated_plan, inserted = maybe_insert_cloud_reconstruction(
                list(current_plan),
                result.result.get("cloud_coverage_pct", 0) / 100,
            )
            if inserted:
                cloud_reconstruction_auto_inserted = True
                current_plan = updated_plan
                step_descriptions = controller.generate_step_descriptions(current_plan)
                yield {
                    "type": "plan_updated",
                    "message": "⚡ Cloud contamination detected! Agent automatically inserted Cloud Reconstruction step.",
                    "new_plan": current_plan,
                    "new_steps": step_descriptions,
                    "inserted_tool": "cloud_reconstruction",
                }

    # ── Evidence aggregation (real, not hardcoded) ────────────────────────────
    from backend.tools.evidence import compute_evidence_strength, LOW_EVIDENCE_THRESHOLD

    tool_results_dicts = [r.model_dump() for r in tool_results_accumulated]
    ev = compute_evidence_strength(tool_results_dicts)
    final_conf = ev.evidence_strength

    session.confidence = final_conf
    session.confidence_level = _compute_confidence_level(final_conf)

    # ── LOW EVIDENCE event ────────────────────────────────────────────────────
    if ev.low_evidence:
        yield {
            "type": "low_evidence",
            "evidence_strength": final_conf,
            "threshold": LOW_EVIDENCE_THRESHOLD,
            "message": (
                f"Evidence strength ({final_conf:.2f}) below threshold ({LOW_EVIDENCE_THRESHOLD}). "
                f"Checking for secondary evidence sources…"
            ),
            "secondary_evidence_status": (
                ev.secondary_evidence_status.value if ev.secondary_evidence_status else
                SecondaryEvidenceStatus.NO_SECONDARY_EVIDENCE_AVAILABLE.value
            ),
            "secondary_evidence_reason": ev.secondary_evidence_reason or (
                "No genuinely independent secondary evidence source is available. "
                "A secondary analysis was NOT manufactured."
            ),
        }
        await asyncio.sleep(0.3)

    # ── Evidence status ───────────────────────────────────────────────────────
    has_conflict = any(
        r.result.get("agreement") is False
        for r in tool_results_accumulated
    )
    session.evidence_status = EvidenceStatus.CONFLICTING if has_conflict else EvidenceStatus.CONSISTENT

    # ── Evidence points (live vs demo clearly labelled) ───────────────────────
    evidence = []
    for r in tool_results_accumulated:
        if r.tool_name not in ("image_validation", "confidence_check", "answer_synthesis", "evidence_comparison"):
            mode = r.execution_mode.value if r.execution_mode else "SIMULATED"
            label = "LIVE" if mode == ExecutionMode.LIVE_ALGORITHM else "DEMO"
            evidence.append(f"[{label}] {r.tool_name.replace('_', ' ').title()}")
    session.evidence_points = evidence

    # ── Final answer ──────────────────────────────────────────────────────────
    answer_tool = get_tool("answer_synthesis")
    answer_context = {
        "demo_scenario": actual_scenario_key,
        "query": query,
        "tool_results": tool_results_dicts,
        "uploaded_images": uploaded_images or [],
    }
    answer_result = answer_tool.timed_run({
        "images": uploaded_images or [],
        "metadata": [],
        "params": {},
        "context": answer_context,
    })
    session.final_answer = answer_result.result.get("final_answer", "")

    # ── Visual outputs ────────────────────────────────────────────────────────
    vis_outputs = []

    # Collect real visual outputs from tools first
    for r in tool_results_accumulated:
        if r.visual_output and r.visual_type:
            if r.tool_name == "bi_temporal_change_detection" and r.visual_type == "change_map":
                vis_outputs.append({
                    "type": "change_map",
                    "label": "Change Map (LIVE_ALGORITHM)",
                    "b64": r.visual_output,
                })
                if r.metadata.get("heatmap_b64"):
                    vis_outputs.append({
                        "type": "confidence_heatmap",
                        "label": "Difference Heatmap (LIVE_ALGORITHM)",
                        "b64": r.metadata["heatmap_b64"],
                    })
            elif r.tool_name == "cloud_detection" and r.visual_type == "cloud_mask":
                vis_outputs.append({
                    "type": "cloud_mask",
                    "label": "Cloud Mask (LIVE_ALGORITHM)",
                    "b64": r.visual_output,
                })
            elif r.tool_name == "cloud_reconstruction" and r.visual_type == "reconstructed":
                vis_outputs.append({
                    "type": "reconstruction",
                    "label": f"Reconstruction ({r.algorithm or 'CPU baseline'})",
                    "b64": r.visual_output,
                })

    # Add input thumbnails if not already represented
    if thumbnails:
        if actual_scenario_key in ("demo1", "demo3"):
            labels = ["Before", "After"]
            if actual_scenario_key == "demo1":
                labels = ["Before (2024)", "After (2026)"]
            elif actual_scenario_key == "demo3":
                labels = ["Before (Jan 2026)", "After (Feb 2026) — Cloud contaminated"]
            for i, (thumb, label) in enumerate(zip(thumbnails, labels)):
                vis_outputs.insert(i, {"type": "before" if i == 0 else "after", "label": label, "b64": thumb})
        elif actual_scenario_key == "demo2":
            vis_outputs.insert(0, {"type": "optical", "label": "Optical (Sentinel-2)", "b64": thumbnails[0]})
            vis_outputs.insert(1, {"type": "sar", "label": "SAR [DEMO] — SAR_NOT_AVAILABLE", "b64": thumbnails[1] if len(thumbnails) > 1 else ""})

    # Demo fallback: add change map if no real one was produced
    if not any(v["type"] == "change_map" for v in vis_outputs):
        if actual_scenario_key in ("demo1", "demo3"):
            vis_outputs.append({
                "type": "change_map",
                "label": "Change Map [DEMO]",
                "b64": demo_imagery.generate_change_map(),
            })
            vis_outputs.append({
                "type": "confidence_heatmap",
                "label": "Confidence Heatmap [DEMO]",
                "b64": demo_imagery.generate_confidence_heatmap(),
            })

    session.visual_outputs = vis_outputs
    session.status = "completed"
    session.completed_at = datetime.utcnow().isoformat()
    SESSION_STORE[session_id] = session

    yield {
        "type": "completed",
        "analysis_id": session_id,
        "confidence": final_conf,
        "confidence_level": session.confidence_level.value,
        "evidence_status": session.evidence_status.value,
        "final_answer": session.final_answer,
        "evidence_points": session.evidence_points,
        "visual_outputs": vis_outputs,
        "conflicts": session.conflicts,
        # Evidence breakdown for the WHY THIS ANSWER panel
        "evidence_breakdown": ev.breakdown,
        "evidence_formula": ev.formula,
        "evidence_interpretation": ev.interpretation,
        "low_evidence": ev.low_evidence,
        "secondary_evidence_status": (
            ev.secondary_evidence_status.value if ev.secondary_evidence_status else None
        ),
        "has_real_images": has_real_images,
    }


def get_session(analysis_id: str) -> Optional[AnalysisSession]:
    return SESSION_STORE.get(analysis_id)
