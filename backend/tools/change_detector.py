"""
SatQuery AI — Real Bi-Temporal Change Detector
Algorithm: abs_diff_otsu_v1

Detects pixel-level changes between two co-registered images using
absolute difference + Otsu thresholding.

Pipeline:
  1. Decode and validate T1, T2
  2. Record original dimensions
  3. Resize T2 to match T1 (if needed)
  4. Attempt ECC registration (registration.py)
  5. If registration FAILED → stop; return UNRELIABLE_REGISTRATION result
  6. Convert registered pair to greyscale
  7. Compute absolute difference
  8. Apply Otsu global threshold → binary change mask
  9. Morphological open (remove speckle) + close (fill holes)
 10. Connected-component filtering (drop components < MIN_AREA_PX²)
 11. Compute changed_area_pct from real mask
 12. Generate heatmap from float difference map

REGISTRATION CONTRACT:
  If registration quality is FAILED:
    → changed_area_pct is NOT computed
    → result dict contains "unreliable_registration": True
    → evidence_excludable is set True in the ToolResult
    → The result is NOT used in evidence scoring

IMPORTANT LABELLING:
  - Algorithm: abs_diff_otsu_v1 (greyscale absolute difference)
  - No NDVI, NDWI, or any spectral index is claimed
  - Greyscale intensity differences only
"""

import base64
import io
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from backend.tools.registration import register_images, RegistrationResult
from backend.schemas.provenance import (
    ExecutionMode, InputProvenance, RegistrationQuality
)


# ── Constants ─────────────────────────────────────────────────────────────────

MIN_AREA_PX = 50     # minimum connected-component area in pixels
MORPH_OPEN_R = 2
MORPH_CLOSE_R = 4


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ChangeDetectionResult:
    """
    Result of bi-temporal change detection.

    If unreliable_registration is True, changed_area_pct MUST NOT be
    presented in the UI or used in evidence scoring.
    """
    # Core result
    changed_area_pct: Optional[float]         # None when registration failed
    changed_pixel_count: Optional[int]
    unchanged_pixel_count: Optional[int]
    total_pixel_count: int

    # Reliability flags
    unreliable_registration: bool             # True → exclude from evidence
    registration_quality: RegistrationQuality
    registration_method: str
    registration_error_px: Optional[float]

    # Imagery
    change_mask_b64: Optional[str]            # None when unreliable
    change_heatmap_b64: Optional[str]         # None when unreliable

    # Dimensions
    t1_shape: Tuple[int, int]                 # (H, W)
    t2_original_shape: Tuple[int, int]
    processed_shape: Tuple[int, int]
    t2_was_resized: bool

    # Provenance
    algorithm: str
    execution_mode: ExecutionMode
    input_provenance: InputProvenance
    processing_time_ms: int

    # Diagnostics
    otsu_threshold: Optional[float]           # 0-255; None when not reached
    message: str
    warnings: list = field(default_factory=list)


# ── Utilities ─────────────────────────────────────────────────────────────────

def _disk_kernel(radius: int) -> np.ndarray:
    d = 2 * radius + 1
    y, x = np.ogrid[-radius:radius + 1, -radius:radius + 1]
    return (x**2 + y**2 <= radius**2).astype(np.uint8)


def _encode_image(arr: np.ndarray) -> str:
    """Encode a uint8 numpy array to base64 PNG."""
    pil = Image.fromarray(arr)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _decode_image(b64: str) -> np.ndarray:
    """Decode base64 to uint8 RGB numpy array."""
    raw = base64.b64decode(b64)
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    return np.array(pil, dtype=np.uint8)


def _build_heatmap(diff_float: np.ndarray) -> str:
    """Convert float difference map [0,1] to a red-hot heatmap base64 PNG."""
    norm = (diff_float * 255).astype(np.uint8)
    # Apply COLORMAP_HOT: black → red → yellow → white
    heatmap_bgr = cv2.applyColorMap(norm, cv2.COLORMAP_HOT)
    heatmap_rgb = cv2.cvtColor(heatmap_bgr, cv2.COLOR_BGR2RGB)
    return _encode_image(heatmap_rgb)


def _annotate_mask(mask: np.ndarray, label: str = "CHANGE MASK  |  LIVE_ALGORITHM") -> str:
    """Add an honest label to the mask before encoding."""
    from PIL import ImageDraw
    pil = Image.fromarray(mask, mode="L").convert("RGB")
    draw = ImageDraw.Draw(pil)
    draw.rectangle([0, 0, 260, 14], fill=(0, 80, 40))
    draw.text((4, 1), label, fill=(255, 255, 255))
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ── Main detection function ───────────────────────────────────────────────────

def detect_change(
    t1_b64: str,
    t2_b64: str,
    input_provenance: InputProvenance = InputProvenance.UNKNOWN,
) -> ChangeDetectionResult:
    """
    Detect pixel-level changes between T1 and T2.

    Args:
        t1_b64: Base64 PNG of earlier-date image.
        t2_b64: Base64 PNG of later-date image.
        input_provenance: Origin of the input images.

    Returns:
        ChangeDetectionResult. Check unreliable_registration before using
        changed_area_pct.
    """
    t_start = time.monotonic()

    # ── Decode ────────────────────────────────────────────────────────────────
    t1 = _decode_image(t1_b64)
    t2 = _decode_image(t2_b64)
    t1_shape = t1.shape[:2]
    t2_original_shape = t2.shape[:2]

    # ── Register ──────────────────────────────────────────────────────────────
    reg: RegistrationResult = register_images(t1, t2)

    # ── REGISTRATION FAILED → stop, do not compute change % ──────────────────
    if reg.quality == RegistrationQuality.FAILED:
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        return ChangeDetectionResult(
            changed_area_pct=None,
            changed_pixel_count=None,
            unchanged_pixel_count=None,
            total_pixel_count=t1.shape[0] * t1.shape[1],
            unreliable_registration=True,
            registration_quality=reg.quality,
            registration_method=reg.method,
            registration_error_px=reg.mean_alignment_error_px,
            change_mask_b64=None,
            change_heatmap_b64=None,
            t1_shape=t1_shape,
            t2_original_shape=t2_original_shape,
            processed_shape=reg.target_shape,
            t2_was_resized=reg.t2_was_resized,
            algorithm="abs_diff_otsu_v1",
            execution_mode=ExecutionMode.LIVE_ALGORITHM,
            input_provenance=input_provenance,
            processing_time_ms=elapsed_ms,
            otsu_threshold=None,
            message=(
                "UNRELIABLE_REGISTRATION: Image registration failed. "
                "Changed-area percentage not computed. "
                "This result is excluded from evidence scoring."
            ),
            warnings=reg.warnings + [
                "Change detection was aborted because registration failed.",
                "Do not report a change percentage from this result.",
            ],
        )

    # ── Use registered T2 ─────────────────────────────────────────────────────
    t2_aligned = reg.registered_image
    warnings = list(reg.warnings)

    if reg.quality == RegistrationQuality.PARTIAL:
        warnings.append(
            f"Registration quality is PARTIAL (error={reg.mean_alignment_error_px:.1f}px). "
            f"Change percentage is computed but flagged as potentially unreliable."
        )

    processed_shape = t1_shape

    # ── Greyscale absolute difference ─────────────────────────────────────────
    def to_grey_uint8(arr: np.ndarray) -> np.ndarray:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    g1 = to_grey_uint8(t1).astype(np.float32)
    g2 = to_grey_uint8(t2_aligned).astype(np.float32)
    diff = np.abs(g1 - g2)                     # float [0, 255]
    diff_norm = diff / 255.0                   # normalised [0, 1]

    diff_uint8 = diff.astype(np.uint8)

    # ── Otsu threshold ────────────────────────────────────────────────────────
    otsu_val, binary_mask = cv2.threshold(
        diff_uint8, 0, 255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    # ── Morphological cleanup ─────────────────────────────────────────────────
    open_k  = _disk_kernel(MORPH_OPEN_R)
    close_k = _disk_kernel(MORPH_CLOSE_R)
    mask_opened = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN,  open_k)
    mask_closed = cv2.morphologyEx(mask_opened,  cv2.MORPH_CLOSE, close_k)

    # ── Connected-component filtering (drop tiny components) ──────────────────
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask_closed, connectivity=8)
    final_mask = np.zeros_like(mask_closed)
    for lbl in range(1, num_labels):  # skip background (label 0)
        area = stats[lbl, cv2.CC_STAT_AREA]
        if area >= MIN_AREA_PX:
            final_mask[labels == lbl] = 255

    # ── Statistics ────────────────────────────────────────────────────────────
    H, W = processed_shape
    total_px = H * W
    changed_px = int(np.sum(final_mask > 0))
    unchanged_px = total_px - changed_px
    changed_pct = round(changed_px / total_px * 100.0, 2)

    # ── Encode outputs ────────────────────────────────────────────────────────
    mask_b64 = _annotate_mask(final_mask)
    heatmap_b64 = _build_heatmap(diff_norm)

    elapsed_ms = int((time.monotonic() - t_start) * 1000)

    unreliable = (reg.quality == RegistrationQuality.PARTIAL)

    return ChangeDetectionResult(
        changed_area_pct=changed_pct,
        changed_pixel_count=changed_px,
        unchanged_pixel_count=unchanged_px,
        total_pixel_count=total_px,
        unreliable_registration=unreliable,
        registration_quality=reg.quality,
        registration_method=reg.method,
        registration_error_px=reg.mean_alignment_error_px,
        change_mask_b64=mask_b64,
        change_heatmap_b64=heatmap_b64,
        t1_shape=t1_shape,
        t2_original_shape=t2_original_shape,
        processed_shape=processed_shape,
        t2_was_resized=reg.t2_was_resized,
        algorithm="abs_diff_otsu_v1",
        execution_mode=ExecutionMode.LIVE_ALGORITHM,
        input_provenance=input_provenance,
        processing_time_ms=elapsed_ms,
        otsu_threshold=float(otsu_val),
        message=(
            f"Change detection complete ({reg.quality.value}). "
            f"Changed area: {changed_pct:.1f}%. "
            f"Registration: {reg.method} ({reg.mean_alignment_error_px or 'n/a'}px error)."
        ),
        warnings=warnings,
    )


# ── Convenience wrapper for tests ─────────────────────────────────────────────

def detect_change_from_arrays(
    t1: np.ndarray,
    t2: np.ndarray,
    input_provenance: InputProvenance = InputProvenance.SYNTHETIC_DATA,
) -> ChangeDetectionResult:
    """Convenience for unit tests — accepts numpy arrays directly."""
    def arr_to_b64(arr: np.ndarray) -> str:
        pil = Image.fromarray(arr.astype(np.uint8), "RGB")
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    return detect_change(arr_to_b64(t1), arr_to_b64(t2), input_provenance)
