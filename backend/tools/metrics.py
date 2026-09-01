"""
SatQuery AI — Real Image Quality Metrics

Computes PSNR and SSIM when a ground-truth reference exists.
Computes IoU, Precision, Recall, F1 for binary masks when a ground-truth mask exists.

POLICY:
  - If reference/ground_truth is None → return MetricResult(available=False)
  - NEVER report a metric when ground truth does not exist
  - NEVER fabricate or estimate accuracy without ground truth
  - Explicitly state when metrics are unavailable

PSNR/SSIM formulas:
  PSNR: 10 * log10(MAX² / MSE), where MAX=255 for uint8
  SSIM: skimage.metrics.structural_similarity (window=7, data_range=255)
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ImageQualityMetrics:
    available: bool
    psnr_db: Optional[float] = None
    ssim: Optional[float] = None
    mse: Optional[float] = None
    reason_unavailable: Optional[str] = None
    formula_psnr: str = "10 * log10(255^2 / MSE) [dB]"
    formula_ssim: str = "skimage.metrics.structural_similarity (window=7, data_range=255)"


@dataclass
class MaskQualityMetrics:
    available: bool
    iou: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    true_positive: Optional[int] = None
    false_positive: Optional[int] = None
    false_negative: Optional[int] = None
    true_negative: Optional[int] = None
    reason_unavailable: Optional[str] = None


# ── Image quality metrics ─────────────────────────────────────────────────────

def compute_image_metrics(
    output: np.ndarray,
    reference: Optional[np.ndarray],
) -> ImageQualityMetrics:
    """
    Compute PSNR and SSIM between output and reference.

    Args:
        output:    Reconstructed/processed image, uint8 [H, W] or [H, W, C].
        reference: Ground-truth image. If None, returns available=False.

    Returns:
        ImageQualityMetrics. Check .available before using metric values.
    """
    if reference is None:
        return ImageQualityMetrics(
            available=False,
            reason_unavailable=(
                "Metric unavailable — ground-truth reference not provided. "
                "PSNR/SSIM cannot be computed without a paired clear-sky reference."
            ),
        )

    # Ensure compatible shapes
    if output.shape != reference.shape:
        return ImageQualityMetrics(
            available=False,
            reason_unavailable=(
                f"Shape mismatch: output {output.shape} vs reference {reference.shape}. "
                f"Cannot compute PSNR/SSIM on mismatched arrays."
            ),
        )

    out_f = output.astype(np.float64)
    ref_f = reference.astype(np.float64)

    # MSE
    mse = float(np.mean((out_f - ref_f) ** 2))

    # PSNR
    if mse == 0.0:
        psnr = float("inf")
    else:
        psnr = float(10.0 * np.log10((255.0 ** 2) / mse))

    # SSIM
    try:
        from skimage.metrics import structural_similarity
        if output.ndim == 3:
            ssim = float(structural_similarity(
                output, reference,
                win_size=7,
                channel_axis=2,
                data_range=255,
            ))
        else:
            ssim = float(structural_similarity(
                output, reference,
                win_size=7,
                data_range=255,
            ))
    except Exception as exc:
        return ImageQualityMetrics(
            available=False,
            reason_unavailable=f"SSIM computation failed: {exc}",
            psnr_db=round(psnr, 3),
            mse=round(mse, 4),
        )

    return ImageQualityMetrics(
        available=True,
        psnr_db=round(psnr, 3),
        ssim=round(ssim, 4),
        mse=round(mse, 4),
    )


# ── Mask quality metrics ──────────────────────────────────────────────────────

def compute_mask_metrics(
    predicted_mask: np.ndarray,
    ground_truth_mask: Optional[np.ndarray],
    threshold: int = 127,
) -> MaskQualityMetrics:
    """
    Compute IoU, Precision, Recall, F1 for a binary mask.

    Args:
        predicted_mask:   Predicted binary mask, uint8. Pixels > threshold → positive.
        ground_truth_mask: GT mask, uint8. If None, returns available=False.
        threshold:         Binarisation threshold (default 127).

    Returns:
        MaskQualityMetrics. Check .available before using metric values.
    """
    if ground_truth_mask is None:
        return MaskQualityMetrics(
            available=False,
            reason_unavailable=(
                "Metric unavailable — no ground-truth cloud mask provided. "
                "IoU/Precision/Recall/F1 cannot be computed."
            ),
        )

    if predicted_mask.shape != ground_truth_mask.shape:
        return MaskQualityMetrics(
            available=False,
            reason_unavailable=(
                f"Shape mismatch: predicted {predicted_mask.shape} vs "
                f"ground_truth {ground_truth_mask.shape}."
            ),
        )

    pred_bin = (predicted_mask > threshold).astype(bool).flatten()
    gt_bin   = (ground_truth_mask > threshold).astype(bool).flatten()

    tp = int(np.sum(pred_bin & gt_bin))
    fp = int(np.sum(pred_bin & ~gt_bin))
    fn = int(np.sum(~pred_bin & gt_bin))
    tn = int(np.sum(~pred_bin & ~gt_bin))

    eps = 1e-8
    precision = tp / (tp + fp + eps)
    recall    = tp / (tp + fn + eps)
    iou       = tp / (tp + fp + fn + eps)
    f1        = 2 * precision * recall / (precision + recall + eps)

    return MaskQualityMetrics(
        available=True,
        iou=round(iou, 4),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        true_negative=tn,
    )
