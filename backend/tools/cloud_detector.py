"""
SatQuery AI — Real RGB Cloud Detector
Algorithm: rgb_cloud_detector_v1

Performs cloud percentage estimation on actual image pixels.
Works on any RGB image (uploaded or loaded from demo assets).

Method:
  1. Convert to float32 [0,1] per channel
  2. Per-pixel brightness = mean(R, G, B)  — high for clouds
  3. Per-pixel whiteness  = 1 - (max - min) / (max + eps)  — high for white/grey clouds
  4. Per-pixel saturation = (max - min) / (max + eps)      — low for clouds
  5. Cloud candidate = brightness > B_THRESH and whiteness > W_THRESH
  6. Morphological opening to remove salt noise (disk radius 3)
  7. Morphological closing to fill small holes (disk radius 5)
  8. Count cloud pixels → cloud_percentage
  9. Return: binary mask (uint8 0/255), cloud_pct, real dimensions

IMPORTANT LIMITATIONS:
  - This is an RGB-only algorithm. It cannot use NIR or thermal bands.
  - Bright sandy/snow surfaces may be false-positives.
  - Deep convective clouds with dark shadows are not detected as cloud.
  - Cloud shadow is NOT detected (requires NIR or thermal).
  
These limitations are explicitly included in every result dict.
"""

import base64
import io
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from backend.schemas.provenance import ExecutionMode, InputProvenance


# ── Tunable thresholds ────────────────────────────────────────────────────────

BRIGHTNESS_THRESHOLD = 0.65   # normalised 0-1; pixels above → cloud candidate
WHITENESS_THRESHOLD  = 0.70   # 0=colourful, 1=perfectly white
MORPH_OPEN_RADIUS    = 3      # px; removes speckle noise
MORPH_CLOSE_RADIUS   = 5      # px; fills small holes in cloud mask


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class CloudDetectionResult:
    cloud_percentage: float
    cloud_pixel_count: int
    clear_pixel_count: int
    total_pixel_count: int
    image_height: int
    image_width: int
    image_channels: int
    cloud_mask_b64: str           # binary mask: white=cloud, black=clear
    algorithm: str
    execution_mode: ExecutionMode
    input_provenance: InputProvenance
    processing_time_ms: int
    requires_reconstruction: bool # True when cloud_percentage >= RECON_THRESHOLD
    quality_rating: str           # "Clear" | "Minor" | "Moderate" | "Severe"
    brightness_threshold_used: float
    whiteness_threshold_used: float
    limitations: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


# ── Threshold → quality label ─────────────────────────────────────────────────

RECON_THRESHOLD = 20.0   # % cloud; matches strategy_registry.CLOUD_THRESHOLD * 100

def _quality_label(pct: float) -> str:
    if pct < 5.0:
        return "Clear"
    elif pct < 20.0:
        return "Minor contamination"
    elif pct < 50.0:
        return "Moderate contamination"
    else:
        return "Severe contamination"


# ── Morphological structuring element ────────────────────────────────────────

def _disk_kernel(radius: int) -> np.ndarray:
    """Circular structuring element for morphological ops."""
    d = 2 * radius + 1
    y, x = np.ogrid[-radius:radius + 1, -radius:radius + 1]
    kernel = (x**2 + y**2 <= radius**2).astype(np.uint8)
    return kernel


# ── Main detection function ───────────────────────────────────────────────────

def detect_clouds_rgb(
    image_b64: str,
    input_provenance: InputProvenance = InputProvenance.UNKNOWN,
    brightness_threshold: float = BRIGHTNESS_THRESHOLD,
    whiteness_threshold: float = WHITENESS_THRESHOLD,
) -> CloudDetectionResult:
    """
    Detect clouds in an RGB image from its base64-encoded PNG/JPEG bytes.

    Args:
        image_b64:             Base64-encoded PNG or JPEG.
        input_provenance:      Where this image came from.
        brightness_threshold:  Tunable; default 0.65.
        whiteness_threshold:   Tunable; default 0.70.

    Returns:
        CloudDetectionResult with real pixel statistics and binary mask.
        On failure, raises ValueError with a descriptive message.
    """
    t_start = time.monotonic()

    # ── Decode image ──────────────────────────────────────────────────────────
    try:
        raw_bytes = base64.b64decode(image_b64)
        pil_img = Image.open(io.BytesIO(raw_bytes))
    except Exception as exc:
        raise ValueError(f"Failed to decode image: {exc}") from exc

    n_channels = len(pil_img.getbands())
    if n_channels not in (1, 3, 4):
        raise ValueError(
            f"Unsupported image mode '{pil_img.mode}' with {n_channels} channels. "
            f"Expected RGB (3) or RGBA (4) or greyscale (1)."
        )

    # Force RGB; drop alpha if present
    pil_rgb = pil_img.convert("RGB")
    img_np = np.array(pil_rgb, dtype=np.float32) / 255.0  # H x W x 3, range [0,1]

    H, W, _ = img_np.shape

    # ── Per-pixel features ────────────────────────────────────────────────────
    R, G, B = img_np[:, :, 0], img_np[:, :, 1], img_np[:, :, 2]

    brightness = (R + G + B) / 3.0
    ch_max = np.max(img_np, axis=2)
    ch_min = np.min(img_np, axis=2)
    ch_range = ch_max - ch_min

    eps = 1e-6
    # Whiteness: 1 for pure white/grey, 0 for vivid colour
    whiteness = 1.0 - (ch_range / (ch_max + eps))

    # ── Cloud candidate mask ──────────────────────────────────────────────────
    cloud_candidate = (brightness > brightness_threshold) & (whiteness > whiteness_threshold)
    cloud_uint8 = cloud_candidate.astype(np.uint8) * 255

    # ── Morphological filtering ────────────────────────────────────────────────
    open_kernel  = _disk_kernel(MORPH_OPEN_RADIUS)
    close_kernel = _disk_kernel(MORPH_CLOSE_RADIUS)
    cloud_opened = cv2.morphologyEx(cloud_uint8, cv2.MORPH_OPEN,  open_kernel)
    cloud_final  = cv2.morphologyEx(cloud_opened, cv2.MORPH_CLOSE, close_kernel)

    # ── Statistics ────────────────────────────────────────────────────────────
    cloud_px = int(np.sum(cloud_final > 0))
    total_px = H * W
    clear_px = total_px - cloud_px
    cloud_pct = round(cloud_px / total_px * 100.0, 2)

    # ── Encode mask as base64 PNG ─────────────────────────────────────────────
    mask_pil = Image.fromarray(cloud_final, mode="L")
    buf = io.BytesIO()
    mask_pil.save(buf, format="PNG")
    mask_b64 = base64.b64encode(buf.getvalue()).decode()

    processing_ms = int((time.monotonic() - t_start) * 1000)

    limitations = [
        "RGB-only: NIR and thermal bands not available — detection relies on brightness and whiteness only.",
        "Bright sand, snow, salt flats, and urban rooftops may cause false positives.",
        "Cloud shadows are NOT detected (requires NIR or thermal).",
        "Thin/semi-transparent clouds may be missed.",
    ]

    warnings = []
    if n_channels == 4:
        warnings.append("Input was RGBA; alpha channel was discarded before processing.")

    return CloudDetectionResult(
        cloud_percentage=cloud_pct,
        cloud_pixel_count=cloud_px,
        clear_pixel_count=clear_px,
        total_pixel_count=total_px,
        image_height=H,
        image_width=W,
        image_channels=n_channels,
        cloud_mask_b64=mask_b64,
        algorithm="rgb_cloud_detector_v1",
        execution_mode=ExecutionMode.LIVE_ALGORITHM,
        input_provenance=input_provenance,
        processing_time_ms=processing_ms,
        requires_reconstruction=cloud_pct >= RECON_THRESHOLD,
        quality_rating=_quality_label(cloud_pct),
        brightness_threshold_used=brightness_threshold,
        whiteness_threshold_used=whiteness_threshold,
        limitations=limitations,
        warnings=warnings,
    )


# ── Utility: decode a raw numpy array directly (for tests) ───────────────────

def detect_clouds_from_array(
    img_np: np.ndarray,
    input_provenance: InputProvenance = InputProvenance.SYNTHETIC_DATA,
) -> CloudDetectionResult:
    """
    Run cloud detection on a numpy uint8 array [H, W, 3].
    Convenience wrapper for unit tests.
    """
    if img_np.dtype != np.uint8:
        img_np = np.clip(img_np, 0, 255).astype(np.uint8)
    pil = Image.fromarray(img_np, "RGB")
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return detect_clouds_rgb(b64, input_provenance)
