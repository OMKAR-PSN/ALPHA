# SatQuery AI 🛰️
### An Interactive Vision-Language Agent for Multimodal Remote Sensing Analysis

> **Prototype v1.0 — Hackathon Demonstration**  
> All demo results are clearly labelled as simulated. This prototype demonstrates system architecture and interaction flow.

---

## What is SatQuery AI?

SatQuery AI lets you ask natural-language questions about satellite imagery. The AI agent decides which remote-sensing tools to use — you never need to specify a model, preprocessing step, or tool manually.

```
USER QUERY
    ↓
CENTRAL CONTROLLER  (understands, plans, selects, orchestrates)
    ↓
SPECIALIST TOOLKIT  (analyses images, detects change, classifies, fuses, reconstructs)
    ↓
CONFIDENCE + EVIDENCE CHECK
    ↓
GROUNDED NATURAL-LANGUAGE ANSWER
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Install Backend Dependencies
```bash
pip install fastapi uvicorn python-multipart pillow numpy opencv-python-headless scikit-image
```

### 2. Start the Backend
```bash
cd c:\Users\Omkar\Desktop\SIH_26
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Install & Start the Frontend
```bash
cd satquery-ai
npm install
npm run dev
```

### 4. Open the App
Navigate to **http://localhost:5173**

---

## Demo Scenarios

Click **"Run Demo"** on any scenario card — no uploads needed.

| # | Title | Query | Key Feature |
|---|-------|-------|-------------|
| 1 | Bi-Temporal Urban Expansion | "Did the built-up area increase near this river between 2024 and 2026?" | Change detection + land cover + spatial reasoning |
| 2 | Optical + SAR Cross-Modal | "Compare the optical and SAR images and identify built-up areas." | Cross-modal fusion + agreement detection |
| 3 | Cloud-Contaminated Analysis | "What changed here? The second image seems hazy." | **Auto cloud reconstruction** — agent inserts step without being asked |

---

## Project Structure

```
SIH_26/
├── backend/
│   ├── main.py                          # FastAPI app + all routes
│   ├── schemas/models.py                # Pydantic data models
│   ├── controller/central_controller.py # Query → structured plan
│   ├── solution_space/strategy_registry.py  # Task → tool workflow
│   ├── knowledge_space/domain_knowledge.py  # RS domain knowledge
│   ├── tools/
│   │   ├── base_tool.py                 # Abstract tool interface
│   │   ├── specialist_tools.py          # All 10 specialist tools
│   │   └── demo_imagery.py              # Procedural image generator
│   └── services/analysis_service.py    # Pipeline orchestration + SSE
│
└── satquery-ai/                         # React + TypeScript + Tailwind
    └── src/
        ├── pages/
        │   ├── HomePage.tsx
        │   ├── AnalysisPage.tsx         # Main 3-column workspace
        │   └── SystemViewPage.tsx       # Architecture diagram
        ├── components/
        │   ├── query/                   # QueryBox, SceneSelector
        │   ├── trace/TracePanel.tsx     # Live animated trace
        │   ├── evidence/EvidencePanel.tsx
        │   ├── visualization/VisualOutputs.tsx  # Before/After slider
        │   └── analysis/FinalAnswerCard.tsx
        ├── api/client.ts                # SSE streaming client
        └── types/index.ts
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/demo/scenarios` | List all demo scenarios |
| `POST` | `/api/demo/run` | Run a preloaded demo (SSE stream) |
| `POST` | `/api/analyze` | Run full analysis (SSE stream) |
| `GET` | `/api/analysis/{id}` | Fetch stored session |
| `GET` | `/api/analysis/{id}/trace` | Fetch tool trace |
| `GET` | `/api/analysis/{id}/results` | Fetch results |
| `POST` | `/api/upload` | Upload image (stub) |

---

## Specialist Toolkit

Every tool implements `BaseTool` and returns a standard `ToolResult`:

```python
{
  "tool_name": str,
  "status": "success" | "warning" | "error",
  "confidence": float,   # 0.0 – 1.0
  "result": dict,
  "visual_output": str,  # base64 PNG
  "visual_type": str,
  "metadata": dict,
  "execution_time_ms": int,
  "is_demo": True        # Always marked in prototype
}
```

| Tool | Purpose |
|------|---------|
| `image_validation` | Format, alignment, metadata checks |
| `cloud_detection` | Cloud coverage analysis |
| `cloud_reconstruction` | SAR-guided infilling of cloud-obscured pixels |
| `scene_understanding` | Scene type + dominant land-cover classification |
| `object_region_detection` | Feature localisation with bounding boxes |
| `land_cover_classification` | Pixel-level classification |
| `bi_temporal_change_detection` | Change map + statistics |
| `sar_optical_fusion` | Cross-modal reasoning + conflict detection |
| `spatial_reasoning` | Distance/adjacency/buffer analysis |
| `evidence_comparison` + `confidence_check` + `answer_synthesis` | Final grounding |

---

## Key Design Decisions

### Controller vs Tools — Clear Separation
```
LLM / Controller:     UNDERSTAND → PLAN → SELECT → ORCHESTRATE → EXPLAIN
Specialist Tools:     ANALYSE → DETECT → CLASSIFY → FUSE → RECONSTRUCT
```

### Dynamic Cloud Reconstruction
Cloud reconstruction is **not** the main product — it's a tool the agent invokes automatically when `cloud_detection` returns coverage ≥ 20%. The user never needs to say "remove clouds first."

### Confidence-First Architecture
- Every tool returns a confidence score
- Cross-tool disagreements are detected (e.g., Optical says "Built-up", SAR says "Water")
- Results below threshold trigger re-analysis (max 2 retries)

### Streaming Architecture
Analysis streams as Server-Sent Events (SSE) so the trace animates in real-time as each tool completes.

---

## Extending the Prototype

### Replacing Mock Tools with Real Models
Each tool is a class implementing `BaseTool`. To swap in a real model:
```python
class LandCoverClassificationTool(BaseTool):
    name = "land_cover_classification"
    is_demo = False  # ← flip this

    def run(self, inputs):
        # Replace with real model call
        result = your_real_model.predict(inputs["images"])
        return self._success(confidence=result.confidence, result=result.data)
```

### Adding an LLM Controller
The `CentralController` has a deterministic routing layer. To add LLM interpretation:
```python
# In central_controller.py
def interpret_query(self, query, image_count):
    # Call Gemini/OpenAI for richer semantic parsing
    llm_response = call_llm(query)
    # Then use deterministic layer as fallback
    ...
```

---

## Disclaimer

All demo results in this prototype are **simulated** using procedurally generated imagery. They are clearly marked with **DEMO DATA** watermarks. No scientific accuracy is claimed. This is an architecture demonstration for a technical hackathon.
