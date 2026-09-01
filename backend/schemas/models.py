"""
SatQuery AI — Pydantic Data Models
All schemas for API request/response and internal data structures.
"""

from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from backend.schemas.provenance import (
    InputProvenance, ExecutionMode, RegistrationQuality, SecondaryEvidenceStatus
)


# ─── Enumerations ────────────────────────────────────────────────────────────

class TaskType(str, Enum):
    SINGLE_IMAGE = "single_image"
    BI_TEMPORAL_CHANGE = "bi_temporal_change"
    SAR_OPTICAL = "sar_optical"
    CLOUD_ANALYSIS = "cloud_analysis"
    OBJECT_DETECTION = "object_detection"
    UNKNOWN = "unknown"


class ToolStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


class EvidenceStatus(str, Enum):
    CONSISTENT = "consistent"
    CONFLICTING = "conflicting"
    INSUFFICIENT = "insufficient"
    PENDING = "pending"


class ConfidenceLevel(str, Enum):
    HIGH = "high"       # >= 0.75
    MEDIUM = "medium"   # >= 0.50
    LOW = "low"         # < 0.50


# ─── Tool Interface ───────────────────────────────────────────────────────────

class ToolResult(BaseModel):
    tool_name: str
    status: ToolStatus = ToolStatus.PENDING
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    result: Dict[str, Any] = Field(default_factory=dict)
    visual_output: Optional[str] = None   # base64 PNG or URL
    visual_type: Optional[str] = None     # "image", "heatmap", "change_map", "mask"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: int = 0
    message: str = ""
    is_demo: bool = True  # True when result is simulated/demo

    # ── Provenance (two-dimensional) ───────────────────────────────────────────
    input_provenance: Optional[InputProvenance] = None
    """Where the input data came from."""

    execution_mode: Optional[ExecutionMode] = None
    """How this result was computed."""

    algorithm: Optional[str] = None
    """Human-readable algorithm/model identifier, e.g. 'rgb_cloud_detector_v1'."""

    registration_quality: Optional[RegistrationQuality] = None
    """Only populated by tools that perform image registration."""

    evidence_excludable: bool = False
    """Set True when a result MUST be excluded from evidence scoring
    (e.g. UNRELIABLE_REGISTRATION or SIMULATED mode)."""

    warnings: List[str] = Field(default_factory=list)
    """Any non-fatal warnings about this result."""

    secondary_evidence_status: Optional[SecondaryEvidenceStatus] = None
    """Populated only when the evidence loop attempted a secondary analysis."""



# ─── Image Input ─────────────────────────────────────────────────────────────

class ImageMetadata(BaseModel):
    image_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = ""
    sensor: str = "Unknown"
    acquisition_date: str = "Unknown"
    image_type: str = "Optical"   # "Optical", "SAR", "Multispectral"
    resolution_m: float = 10.0
    width_px: int = 0
    height_px: int = 0
    cloud_coverage_pct: float = 0.0
    cloud_status: str = "Unknown"  # "Clear", "Detected", "Reconstructed"
    processing_status: str = "Ready"
    coordinates: Optional[str] = None
    base64_thumbnail: Optional[str] = None


# ─── Analysis Session ─────────────────────────────────────────────────────────

class AnalysisInput(BaseModel):
    role: str   # "primary", "reference", "sar", "temporal_before", "temporal_after"
    image_id: str
    metadata: ImageMetadata


class TraceStep(BaseModel):
    step_index: int
    step_name: str
    description: str
    status: ToolStatus = ToolStatus.PENDING
    tool_name: Optional[str] = None
    tool_result: Optional[ToolResult] = None
    timestamp: Optional[str] = None
    is_auto_inserted: bool = False  # True when controller inserted this step dynamically


class AnalysisSession(BaseModel):
    analysis_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    inputs: List[AnalysisInput] = Field(default_factory=list)
    task_type: TaskType = TaskType.UNKNOWN
    intent: str = ""
    plan: List[str] = Field(default_factory=list)  # ordered tool names
    trace: List[TraceStep] = Field(default_factory=list)
    tool_results: List[ToolResult] = Field(default_factory=list)
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    evidence_status: EvidenceStatus = EvidenceStatus.PENDING
    reanalysis_count: int = 0
    max_reanalysis: int = 2
    final_answer: str = ""
    evidence_points: List[str] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    visual_outputs: List[Dict[str, str]] = Field(default_factory=list)
    status: str = "pending"  # "pending", "running", "completed", "error"
    error_message: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    is_demo: bool = False


# ─── Request/Response Models ──────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    query: str
    image_ids: List[str] = Field(default_factory=list)
    demo_scenario: Optional[str] = None   # "demo1", "demo2", "demo3"


class DemoRunRequest(BaseModel):
    scenario_id: str   # "demo1", "demo2", "demo3"
    query: Optional[str] = None  # override default query


class DemoScenario(BaseModel):
    scenario_id: str
    title: str
    description: str
    default_query: str
    task_type: TaskType
    images: List[ImageMetadata]
    tags: List[str] = Field(default_factory=list)


class ControllerPlan(BaseModel):
    task_type: TaskType
    intent: str
    target: str
    spatial_reference: Optional[str] = None
    temporal: bool = False
    dates: List[str] = Field(default_factory=list)
    requires_sar: bool = False
    tools: List[str] = Field(default_factory=list)
    reasoning: str = ""


class AnalysisStatusResponse(BaseModel):
    analysis_id: str
    status: str
    progress_pct: float = 0.0
    current_step: Optional[str] = None
    trace: List[TraceStep] = Field(default_factory=list)
    tool_results: List[ToolResult] = Field(default_factory=list)
    confidence: float = 0.0
    evidence_status: EvidenceStatus = EvidenceStatus.PENDING
    final_answer: str = ""
    evidence_points: List[str] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    visual_outputs: List[Dict[str, str]] = Field(default_factory=list)
    error_message: str = ""
