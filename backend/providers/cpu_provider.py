"""
SatQuery AI — CPU Inpainting Provider

Uses OpenCV Telea (INPAINT_TELEA) inpainting as a lightweight CPU baseline
for cloud reconstruction.

IMPORTANT LABELLING:
  - Method: OpenCV Telea / Navier-Stokes
  - Execution: LIVE_ALGORITHM (runs on actual pixels right now)
  - Purpose: CPU baseline for demo reliability
  - NOT equivalent to EMRDM or any learned diffusion model
  - Results are honest CPU inpainting, not deep learning reconstruction

Works on any uploaded image — no scene_id match required.
"""

import base64
import io
import time
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from backend.providers.base import BaseProvider, ProviderResult
from backend.schemas.provenance import ExecutionMode, InputProvenance


class CPUInpaintingProvider(BaseProvider):
    """
    OpenCV-based inpainting provider.

    Supports two OpenCV algorithms:
      - INPAINT_TELEA (default): fast, artifact-free for small masks
      - INPAINT_NS  (Navier-Stokes): better for larger regions but slower

    The chosen algorithm is documented in the returned ProviderResult.
    """

    INPAINT_RADIUS = 10  # pixels
    LARGE_MASK_THRESHOLD = 0.30  # switch to NS above 30% mask coverage

    @property
    def name(self) -> str:
        return "CPUInpaintingProvider"

    def is_available(self) -> bool:
        """Always available — depends only on opencv-python-headless."""
        try:
            cv2.inpaint  # noqa: B018 — just checking import
            return True
        except AttributeError:
            return False

    def reconstruct(
        self,
        image_b64: str,
        mask_b64: str,
        scene_id: Optional[str] = None,
        input_provenance: InputProvenance = InputProvenance.UNKNOWN,
    ) -> ProviderResult:
        """
        Inpaint cloud-masked pixels using OpenCV.

        The mask must be a binary image where white (255) = cloud pixels
        and black (0) = clear pixels. If mask is RGB, it is converted to
        single-channel by taking the maximum across channels.
        """
        start_ms = time.monotonic()

        try:
            # Decode source image
            img_bytes = base64.b64decode(image_b64)
            pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            img_np = np.array(pil_img, dtype=np.uint8)

            # Decode mask
            mask_bytes = base64.b64decode(mask_b64)
            pil_mask = Image.open(io.BytesIO(mask_bytes))
            mask_np = np.array(pil_mask)

            # Normalise mask to single-channel uint8
            if mask_np.ndim == 3:
                mask_1ch = np.max(mask_np, axis=2)
            else:
                mask_1ch = mask_np

            # Binarise: any pixel > 127 is treated as cloud
            _, binary_mask = cv2.threshold(mask_1ch.astype(np.uint8), 127, 255, cv2.THRESH_BINARY)

            # Choose algorithm based on mask coverage
            mask_coverage = np.mean(binary_mask > 0)
            if mask_coverage > self.LARGE_MASK_THRESHOLD:
                flags = cv2.INPAINT_NS
                algo_name = "opencv_navier_stokes_inpaint"
                algo_note = "Navier-Stokes (large mask)"
            else:
                flags = cv2.INPAINT_TELEA
                algo_name = "opencv_telea_inpaint"
                algo_note = "Telea (small/medium mask)"

            # Inpaint
            result_np = cv2.inpaint(img_np, binary_mask, self.INPAINT_RADIUS, flags)

            # Annotate output with honest label
            pil_result = Image.fromarray(result_np)
            from PIL import ImageDraw
            draw = ImageDraw.Draw(pil_result)
            draw.rectangle([0, 0, 300, 16], fill=(0, 100, 60))
            draw.text(
                (4, 2),
                f"CPU BASELINE: {algo_note}  |  NOT EMRDM",
                fill=(255, 255, 255),
            )

            # Encode output
            buf = io.BytesIO()
            pil_result.save(buf, format="PNG")
            output_b64 = base64.b64encode(buf.getvalue()).decode()

            runtime_ms = int((time.monotonic() - start_ms) * 1000)

            return ProviderResult(
                output_b64=output_b64,
                execution_mode=ExecutionMode.LIVE_ALGORITHM,
                algorithm=algo_name,
                input_provenance=input_provenance,
                success=True,
                message=(
                    f"CPU inpainting complete ({algo_note}). "
                    f"Mask coverage: {mask_coverage*100:.1f}%. "
                    f"This is a lightweight CPU baseline — NOT EMRDM."
                ),
                runtime_ms=runtime_ms,
                model_id=None,
                checkpoint=None,
                warnings=[
                    "Result is OpenCV inpainting, not a learned diffusion model.",
                    "Quality degrades significantly for large masked areas (>30%).",
                ] if mask_coverage > 0.20 else [
                    "Result is OpenCV inpainting, not a learned diffusion model.",
                ],
            )

        except Exception as exc:
            return ProviderResult(
                output_b64="",
                execution_mode=ExecutionMode.LIVE_ALGORITHM,
                algorithm="opencv_telea_inpaint",
                input_provenance=input_provenance,
                success=False,
                message=f"CPU inpainting failed: {exc}",
                warnings=[str(exc)],
            )
