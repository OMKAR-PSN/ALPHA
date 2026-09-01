"""
SatQuery AI — Image Registration Module

Attempts to spatially align two images (T2 onto T1) before bi-temporal
change detection. Good registration is required for reliable change maps.

If registration fails or the alignment error is above an acceptable threshold,
the RegistrationResult.quality is set to FAILED or PARTIAL, and the caller
MUST honour the constraint below:

  CONSTRAINT: If quality == FAILED:
    → do NOT compute or report a change-area percentage.
    → mark the change result as UNRELIABLE_REGISTRATION.
    → exclude that result from evidence scoring.

Algorithm:
  1. Convert both images to greyscale
  2. Resize T2 to match T1 dimensions (record scale)
  3. Attempt ECC (Enhanced Correlation Coefficient) with MOTION_TRANSLATION
  4. If ECC diverges or has high mean_alignment_error:
       fall back to MOTION_AFFINE (slower, more general)
  5. If both fail: return quality=FAILED
  6. If ECC converges but mean error > STRICT_ERROR_THRESHOLD:
       return quality=PARTIAL with a clear warning

ECC references:
  Evangelidis & Psarakis (2008) — "Parametric Image Alignment Using Enhanced
  Correlation Coefficient Maximization", IEEE TPAMI.
"""

import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

import cv2
import numpy as np

from backend.schemas.provenance import RegistrationQuality


# ── Tunable constants ─────────────────────────────────────────────────────────

ECC_MAX_ITER = 200
ECC_EPSILON  = 1e-5
STRICT_ERROR_THRESHOLD = 5.0   # pixels; above this → PARTIAL quality
FAILED_THRESHOLD       = 15.0  # pixels; above this → FAILED quality


# ── Result data class ─────────────────────────────────────────────────────────

@dataclass
class RegistrationResult:
    """
    Outcome of image registration.

    The `registered_image` field should only be used for change detection
    when quality == SUCCESS or PARTIAL.
    When quality == FAILED, callers MUST NOT use registered_image for
    quantitative change analysis.
    """
    registered_image: Optional[np.ndarray]  # None when quality==FAILED
    quality: RegistrationQuality
    method: str       # e.g. "ECC_TRANSLATION" | "ECC_AFFINE" | "FAILED"
    mean_alignment_error_px: Optional[float]  # None when not measurable
    warp_matrix: Optional[np.ndarray]         # None when failed
    t2_was_resized: bool
    original_t2_shape: Tuple[int, int]        # (H, W) before resize
    target_shape: Tuple[int, int]             # (H, W) of T1 (output aligned to this)
    processing_time_ms: int
    message: str
    warnings: list = field(default_factory=list)


# ── Utility ───────────────────────────────────────────────────────────────────

def _to_grey(img: np.ndarray) -> np.ndarray:
    """Convert uint8 array to single-channel float32 [0,1] for ECC."""
    if img.ndim == 3 and img.shape[2] >= 3:
        grey = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    elif img.ndim == 2:
        grey = img
    else:
        grey = img[:, :, 0]
    return grey.astype(np.float32)


def _mean_reprojection_error(img1_grey: np.ndarray, img2_warped: np.ndarray) -> float:
    """
    Estimate mean absolute per-pixel difference after alignment.
    Used as a proxy for registration quality.
    Lower = better alignment.
    """
    diff = np.abs(img1_grey.astype(np.float32) - img2_warped.astype(np.float32))
    return float(np.mean(diff))


def _apply_warp(
    img: np.ndarray,
    warp_matrix: np.ndarray,
    target_shape: Tuple[int, int],
    motion_type: int,
) -> np.ndarray:
    """Warp a colour image using the computed warp matrix."""
    H, W = target_shape
    if motion_type == cv2.MOTION_TRANSLATION or motion_type == cv2.MOTION_EUCLIDEAN:
        warped = cv2.warpAffine(
            img, warp_matrix, (W, H),
            flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
        )
    elif motion_type == cv2.MOTION_AFFINE:
        warped = cv2.warpAffine(
            img, warp_matrix, (W, H),
            flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
        )
    else:
        warped = cv2.warpPerspective(
            img, warp_matrix, (W, H),
            flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
        )
    return warped


# ── Core registration function ────────────────────────────────────────────────

def register_images(
    t1: np.ndarray,
    t2: np.ndarray,
) -> RegistrationResult:
    """
    Register t2 onto t1 using ECC.

    Args:
        t1: Reference image, uint8 [H, W] or [H, W, C]
        t2: Target image to align, uint8 [H, W] or [H, W, C]

    Returns:
        RegistrationResult — check .quality before using .registered_image.

    IMPORTANT:
        If result.quality == FAILED, the caller MUST mark any subsequent
        change detection as UNRELIABLE_REGISTRATION and exclude it from
        evidence scoring.
    """
    t_start = time.monotonic()
    original_t2_shape = t2.shape[:2]
    target_shape = t1.shape[:2]
    warnings = []
    t2_was_resized = False

    # ── Resize T2 to match T1 if dimensions differ ────────────────────────────
    if t2.shape[:2] != target_shape:
        warnings.append(
            f"T2 dimensions {t2.shape[:2]} differ from T1 {target_shape}. "
            f"T2 resized to match T1 — check that aspect ratio and GSD are compatible."
        )
        t2_was_resized = True
        t2 = cv2.resize(t2, (target_shape[1], target_shape[0]), interpolation=cv2.INTER_AREA)

    g1 = _to_grey(t1)
    g2 = _to_grey(t2)

    H, W = target_shape

    # ── Attempt 1: ECC Translation ────────────────────────────────────────────
    warp_matrix_transl = np.eye(2, 3, dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, ECC_MAX_ITER, ECC_EPSILON)

    try:
        _, warp_t = cv2.findTransformECC(
            g1, g2, warp_matrix_transl, cv2.MOTION_TRANSLATION, criteria,
        )
        t2_warped_grey = cv2.warpAffine(
            g2, warp_t, (W, H),
            flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
        )
        error_t = _mean_reprojection_error(g1, t2_warped_grey)
        method_t = "ECC_TRANSLATION"
        success_t = True
    except cv2.error:
        warp_t, error_t, success_t, method_t = None, float("inf"), False, "ECC_TRANSLATION"

    # ── Attempt 2: ECC Affine (if translation failed or had large error) ──────
    run_affine = (not success_t) or (error_t > STRICT_ERROR_THRESHOLD)
    warp_matrix_affine = np.eye(2, 3, dtype=np.float32)
    success_a = False
    warp_a, error_a, method_a = None, float("inf"), "ECC_AFFINE"

    if run_affine:
        try:
            _, warp_a = cv2.findTransformECC(
                g1, g2, warp_matrix_affine, cv2.MOTION_AFFINE, criteria,
            )
            t2_warped_grey_a = cv2.warpAffine(
                g2, warp_a, (W, H),
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
            )
            error_a = _mean_reprojection_error(g1, t2_warped_grey_a)
            method_a = "ECC_AFFINE"
            success_a = True
        except cv2.error:
            pass

    # ── Choose best result ─────────────────────────────────────────────────────
    if success_t and (not run_affine or error_t <= error_a):
        best_warp = warp_t
        best_error = error_t
        best_method = method_t
        motion_type = cv2.MOTION_TRANSLATION
    elif success_a:
        best_warp = warp_a
        best_error = error_a
        best_method = method_a
        motion_type = cv2.MOTION_AFFINE
    else:
        # Both failed
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        return RegistrationResult(
            registered_image=None,
            quality=RegistrationQuality.FAILED,
            method="FAILED",
            mean_alignment_error_px=None,
            warp_matrix=None,
            t2_was_resized=t2_was_resized,
            original_t2_shape=original_t2_shape,
            target_shape=target_shape,
            processing_time_ms=elapsed_ms,
            message=(
                "ECC registration failed to converge for both translation and affine models. "
                "Change detection result MUST be marked UNRELIABLE_REGISTRATION."
            ),
            warnings=warnings + [
                "ECC_TRANSLATION did not converge.",
                "ECC_AFFINE did not converge.",
                "Possible causes: insufficient texture, large baseline, very different appearance.",
            ],
        )

    # ── Determine quality ─────────────────────────────────────────────────────
    if best_error > FAILED_THRESHOLD:
        quality = RegistrationQuality.FAILED
        warnings.append(
            f"Registration error {best_error:.1f}px exceeds FAILED threshold "
            f"({FAILED_THRESHOLD}px). Using this result for change detection is invalid."
        )
        registered_image = None
    elif best_error > STRICT_ERROR_THRESHOLD:
        quality = RegistrationQuality.PARTIAL
        warnings.append(
            f"Registration error {best_error:.1f}px exceeds strict threshold "
            f"({STRICT_ERROR_THRESHOLD}px). Change detection results flagged as PARTIAL quality."
        )
        registered_image = _apply_warp(t2, best_warp, target_shape, motion_type)
    else:
        quality = RegistrationQuality.SUCCESS
        registered_image = _apply_warp(t2, best_warp, target_shape, motion_type)

    elapsed_ms = int((time.monotonic() - t_start) * 1000)

    return RegistrationResult(
        registered_image=registered_image,
        quality=quality,
        method=best_method,
        mean_alignment_error_px=round(best_error, 3),
        warp_matrix=best_warp,
        t2_was_resized=t2_was_resized,
        original_t2_shape=original_t2_shape,
        target_shape=target_shape,
        processing_time_ms=elapsed_ms,
        message=(
            f"Registration {quality.value.lower()} via {best_method}. "
            f"Mean alignment error: {best_error:.1f}px."
        ),
        warnings=warnings,
    )
