"""
SatQuery AI — Provenance & Execution Mode Enumerations

Every ToolResult must declare:
  - input_provenance: where the input data came from
  - execution_mode:   how the result was computed

These two dimensions let judges (and the system itself) distinguish
LIVE real computation from demos and deferred GPU outputs.
"""

from enum import Enum


class InputProvenance(str, Enum):
    """Describes the origin of the input data fed to a tool."""

    REAL_SATELLITE_DATA = "REAL_SATELLITE_DATA"
    """Actual satellite imagery obtained from an operational provider (e.g. Bhoonidhi)."""

    BENCHMARK_DATA = "BENCHMARK_DATA"
    """Data from a published benchmark dataset with known provenance and licence."""

    SYNTHETIC_DATA = "SYNTHETIC_DATA"
    """Procedurally generated imagery used for automated tests and fallback demos.
    Must NOT be presented as primary evidence of remote-sensing capability."""

    DEMO_ASSET = "DEMO_ASSET"
    """A pre-verified output stored in data/demo/ for a predefined scene only.
    Must NEVER be returned for an arbitrary or user-uploaded image."""

    USER_UPLOAD = "USER_UPLOAD"
    """An image uploaded by the user during the current session."""

    UNKNOWN = "UNKNOWN"
    """Provenance cannot be determined — treat as lowest trust."""


class ExecutionMode(str, Enum):
    """Describes how a tool's result was computed."""

    LIVE_ALGORITHM = "LIVE_ALGORITHM"
    """A deterministic, CPU-executable algorithm running on the actual input pixels.
    Results are reproducible and can be verified."""

    LIVE_MODEL = "LIVE_MODEL"
    """A trained ML model running inference right now on the current machine."""

    REMOTE_MODEL = "REMOTE_MODEL"
    """Inference delegated to a remote GPU endpoint.
    Results are live but computed externally."""

    PRECOMPUTED_MODEL_OUTPUT = "PRECOMPUTED_MODEL_OUTPUT"
    """Result was produced by a model on another machine/time and stored as a verified asset.
    Valid ONLY for predefined demo scenes where the manifest is present.
    MUST NOT be returned for user-uploaded or arbitrary images."""

    SIMULATED = "SIMULATED"
    """Result is procedurally generated for demonstration purposes.
    Must be clearly labelled as such in every UI surface."""


class RegistrationQuality(str, Enum):
    """Outcome of image registration — used for evidence scoring."""

    SUCCESS = "SUCCESS"
    """Registration converged within acceptable error bounds."""

    PARTIAL = "PARTIAL"
    """Registration converged but error exceeds strict threshold — results flagged."""

    FAILED = "FAILED"
    """Registration did not converge. Change-area percentage is UNRELIABLE."""

    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    """Registration was not required (single-image analysis) or not applicable."""

    NOT_REQUIRED = "NOT_REQUIRED"
    """Spatial alignment not needed for this tool (e.g. single-image cloud detection)."""


class SecondaryEvidenceStatus(str, Enum):
    """Result of attempting to find genuinely independent secondary evidence."""

    CONFIRMED = "CONFIRMED"
    """A real independent evidence source was found and run."""

    NO_SECONDARY_EVIDENCE_AVAILABLE = "NO_SECONDARY_EVIDENCE_AVAILABLE"
    """No independent secondary method or data source exists for this input.
    The system does NOT manufacture secondary analysis to trigger a demo flow."""

    SECONDARY_INCONCLUSIVE = "SECONDARY_INCONCLUSIVE"
    """Secondary analysis ran but could not resolve the uncertainty."""
