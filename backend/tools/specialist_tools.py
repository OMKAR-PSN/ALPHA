"""
SatQuery AI — Specialist Tools (Real + Demo fallback)

Each tool follows a two-path strategy:
  REAL path:  runs when a LoadedScene with real/uploaded image data is provided
  DEMO path:  runs when no real image is attached (uses procedural demo_imagery)

Tools that have real implementations:
  - ImageValidationTool   → validates actual image properties
  - CloudDetectionTool    → rgb_cloud_detector_v1 on real pixels
  - CloudReconstructionTool → CPUInpaintingProvider (or Precomputed/RemoteGPU)
  - BiTemporalChangeDetectionTool → abs_diff_otsu_v1 with ECC registration

Tools that remain SIMULATED (labelled explicitly):
  - SceneUnderstandingTool       → requires land-cover model
  - ObjectRegionDetectionTool    → requires object detection model
  - LandCoverClassificationTool  → requires spectral data + classifier
  - SarOpticalFusionTool         → no real SAR input available → SAR_NOT_AVAILABLE
  - SpatialReasoningTool         → requires real georeference
  - EvidenceComparisonTool       → upgraded to use evidence.py
  - ConfidenceCheckTool          → upgraded to use evidence.py
  - AnswerSynthesisTool          → canned answers (reliable for demo)
"""

import time
import random
import base64
import io
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image

from backend.tools.base_tool import BaseTool
from backend.schemas.models import ToolResult, ToolStatus
from backend.schemas.provenance import (
    ExecutionMode, InputProvenance, RegistrationQuality, SecondaryEvidenceStatus
)
from backend.tools import demo_imagery


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_scene_b64(inputs: Dict[str, Any], index: int = 0) -> Optional[str]:
    """
    Extract a base64 image string from tool inputs.
    Returns None if no real image is available.
    """
    images = inputs.get("images", [])
    if images and index < len(images):
        img = images[index]
        if isinstance(img, str) and len(img) > 100:
            return img
    # Also check context for uploaded images
    context = inputs.get("context", {})
    uploaded = context.get("uploaded_images", [])
    if uploaded and index < len(uploaded):
        return uploaded[index]
    return None


def _has_real_images(inputs: Dict[str, Any]) -> bool:
    return _extract_scene_b64(inputs, 0) is not None


# ─── 1. Image Validation ──────────────────────────────────────────────────────

class ImageValidationTool(BaseTool):
    name = "image_validation"
    description = "Validates image format, dimensions, channels, and pair alignment."
    is_demo = False

    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        images_b64 = [_extract_scene_b64(inputs, i) for i in range(4)]
        images_b64 = [b for b in images_b64 if b is not None]

        if not images_b64:
            # Demo fallback — no real images attached
            n = len(inputs.get("context", {}).get("demo_images", [])) or 2
            return self._success(
                confidence=0.95,
                result={
                    "images_received": n,
                    "all_valid": True,
                    "alignment_check": "passed" if n > 1 else "single_image",
                    "format_check": "passed",
                    "dimension_check": "passed",
                    "issues": [],
                    "note": "No real image attached — validation is a metadata check only.",
                },
                message=f"{n} image(s) registered for analysis.",
                metadata={
                    "execution_mode": ExecutionMode.SIMULATED,
                    "input_provenance": InputProvenance.SYNTHETIC_DATA,
                },
            )

        # Real validation
        issues = []
        image_infos = []
        for idx, b64 in enumerate(images_b64):
            try:
                raw = base64.b64decode(b64)
                pil = Image.open(io.BytesIO(raw))
                image_infos.append({
                    "index": idx,
                    "mode": pil.mode,
                    "width": pil.width,
                    "height": pil.height,
                    "n_channels": len(pil.getbands()),
                })
            except Exception as exc:
                issues.append(f"Image {idx}: decode failed — {exc}")

        # Alignment check for pairs
        alignment = "single_image"
        if len(image_infos) >= 2:
            sizes = set((i["width"], i["height"]) for i in image_infos)
            alignment = "passed" if len(sizes) == 1 else "mismatched_dimensions"
            if len(sizes) > 1:
                issues.append(f"Image dimensions differ: {sizes}")

        all_valid = len(issues) == 0
        result = {
            "images_received": len(images_b64),
            "all_valid": all_valid,
            "alignment_check": alignment,
            "format_check": "passed" if all_valid else "failed",
            "dimension_check": alignment,
            "image_details": image_infos,
            "issues": issues,
        }

        tr = self._success(
            confidence=0.98 if all_valid else 0.5,
            result=result,
            message=(
                f"{len(images_b64)} image(s) validated successfully."
                if all_valid
                else f"Validation issues: {'; '.join(issues)}"
            ),
        )
        tr.is_demo = False
        tr.execution_mode = ExecutionMode.LIVE_ALGORITHM
        tr.input_provenance = InputProvenance.USER_UPLOAD
        tr.algorithm = "pillow_image_validator_v1"
        return tr


# ─── 2. Cloud Detection ───────────────────────────────────────────────────────

class CloudDetectionTool(BaseTool):
    name = "cloud_detection"
    description = "Detects cloud coverage in optical satellite imagery."
    is_demo = False

    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        context = inputs.get("context", {})
        demo_scenario = context.get("demo_scenario", "demo1")
        
        loaded_scenes = inputs.get("loaded_scenes", [])
        if loaded_scenes:
            prov = getattr(loaded_scenes[0], "input_provenance", InputProvenance.UNKNOWN)
            return self._run_real(loaded_scenes[0].image_b64, provenance=prov)
            
        image_b64 = _extract_scene_b64(inputs, 0)
        if image_b64:
            return self._run_real(image_b64)
        else:
            return self._run_demo(demo_scenario)

    def _run_real(self, image_b64: str, provenance: InputProvenance = InputProvenance.USER_UPLOAD) -> ToolResult:
        from backend.tools.cloud_detector import detect_clouds_rgb
        try:
            cdr = detect_clouds_rgb(image_b64, provenance)
            status = ToolStatus.WARNING if cdr.cloud_percentage >= 20.0 else ToolStatus.SUCCESS
            result = {
                "cloud_coverage_pct": cdr.cloud_percentage,
                "cloud_pixel_count": cdr.cloud_pixel_count,
                "clear_pixel_count": cdr.clear_pixel_count,
                "total_pixel_count": cdr.total_pixel_count,
                "requires_reconstruction": cdr.requires_reconstruction,
                "quality_rating": cdr.quality_rating,
                "image_dimensions": [cdr.image_height, cdr.image_width],
                "limitations": cdr.limitations,
            }
            tr = ToolResult(
                tool_name=self.name,
                status=status,
                confidence=0.80,
                result=result,
                visual_output=cdr.cloud_mask_b64,
                visual_type="cloud_mask",
                message=(
                    f"Cloud detection complete. {cdr.cloud_percentage:.1f}% cloud coverage detected. "
                    f"Algorithm: {cdr.algorithm}."
                ),
                is_demo=False,
                execution_mode=ExecutionMode.LIVE_ALGORITHM,
                input_provenance=provenance,
                algorithm=cdr.algorithm,
                warnings=cdr.warnings + cdr.limitations,
            )
            tr.execution_time_ms = cdr.processing_time_ms
            return tr
        except Exception as exc:
            return self._error(f"Real cloud detection failed: {exc}")

    def _run_demo(self, demo_scenario: str) -> ToolResult:
        if demo_scenario == "demo3":
            coverage = 0.38
            cloud_img = demo_imagery.generate_cloud_image()
            cloud_mask = demo_imagery.generate_cloud_mask()
            status = ToolStatus.WARNING
            msg = "Significant cloud contamination detected (38%). Reconstruction recommended. [DEMO]"
            conf = 0.82
        else:
            coverage = 0.04
            cloud_img = None
            cloud_mask = None
            status = ToolStatus.SUCCESS
            msg = "Minimal cloud coverage (4%). Images suitable for analysis. [DEMO]"
            conf = 0.85

        result = {
            "cloud_coverage_pct": round(coverage * 100, 1),
            "cloud_pixel_count": int(512 * 512 * coverage),
            "clear_pixel_count": int(512 * 512 * (1 - coverage)),
            "requires_reconstruction": coverage >= 0.20,
            "quality_rating": "Poor" if coverage > 0.30 else "Good" if coverage < 0.10 else "Fair",
            "limitations": ["DEMO mode — no real image attached. Values are scenario-specific."],
        }
        tr = ToolResult(
            tool_name=self.name,
            status=status,
            confidence=conf,
            result=result,
            visual_output=cloud_img,
            visual_type="cloud_overlay" if coverage >= 0.20 else None,
            metadata={"mask_b64": cloud_mask} if cloud_mask else {},
            message=msg,
            is_demo=True,
            execution_mode=ExecutionMode.SIMULATED,
            input_provenance=InputProvenance.SYNTHETIC_DATA,
            algorithm="demo_scenario_lookup",
        )
        return tr


# ─── 3. Cloud Reconstruction ──────────────────────────────────────────────────

class CloudReconstructionTool(BaseTool):
    name = "cloud_reconstruction"
    description = "Reconstructs cloud-obscured pixels. CPU baseline: OpenCV inpainting."
    is_demo = False

    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        context = inputs.get("context", {})
        image_b64  = _extract_scene_b64(inputs, 0)
        mask_b64   = context.get("cloud_mask_b64")
        scene_id   = context.get("scene_id")
        input_prov = InputProvenance.USER_UPLOAD if image_b64 else InputProvenance.SYNTHETIC_DATA

        if image_b64 and mask_b64:
            return self._run_real(image_b64, mask_b64, scene_id, input_prov)
        elif image_b64 and not mask_b64:
            # Auto-detect cloud mask from the image
            return self._run_real_with_detection(image_b64, scene_id, input_prov)
        else:
            return self._run_demo()

    def _run_real(self, image_b64: str, mask_b64: str, scene_id: Optional[str], prov: InputProvenance) -> ToolResult:
        from backend.providers.provider_factory import get_reconstruction_provider
        provider = get_reconstruction_provider(scene_id)
        pr = provider.reconstruct(image_b64, mask_b64, scene_id, prov)

        result = {
            "method": pr.algorithm,
            "provider": provider.name,
            "execution_mode": pr.execution_mode.value,
            "success": pr.success,
            "runtime_ms": pr.runtime_ms,
            "model_id": pr.model_id,
            "note": pr.message,
        }
        if not pr.success:
            return self._error(pr.message)

        tr = self._success(
            confidence=0.70,
            result=result,
            message=pr.message,
            visual_output=pr.output_b64,
            visual_type="reconstructed",
        )
        tr.is_demo = False
        tr.execution_mode = pr.execution_mode
        tr.input_provenance = prov
        tr.algorithm = pr.algorithm
        tr.warnings = pr.warnings
        return tr

    def _run_real_with_detection(self, image_b64: str, scene_id: Optional[str], prov: InputProvenance) -> ToolResult:
        from backend.tools.cloud_detector import detect_clouds_rgb
        try:
            cdr = detect_clouds_rgb(image_b64, prov)
            if cdr.cloud_percentage < 5.0:
                return self._success(
                    confidence=0.90,
                    result={"note": "Cloud coverage < 5% — reconstruction not needed.", "cloud_pct": cdr.cloud_percentage},
                    message="Cloud coverage too low to require reconstruction.",
                )
            return self._run_real(image_b64, cdr.cloud_mask_b64, scene_id, prov)
        except Exception as exc:
            return self._error(f"Auto-detect + reconstruction failed: {exc}")

    def _run_demo(self) -> ToolResult:
        time.sleep(0.2)
        reconstructed = demo_imagery.generate_reconstructed_image()
        result = {
            "method": "DEMO — no real image attached",
            "execution_mode": ExecutionMode.SIMULATED.value,
            "note": (
                "No real image provided. Demo reconstruction shown. "
                "Connect a real image for actual CPU inpainting."
            ),
        }
        tr = self._success(
            confidence=0.60,
            result=result,
            message="Demo reconstruction (no real image). [DEMO]",
            visual_output=reconstructed,
            visual_type="reconstructed",
        )
        tr.is_demo = True
        tr.execution_mode = ExecutionMode.SIMULATED
        tr.input_provenance = InputProvenance.SYNTHETIC_DATA
        tr.algorithm = "demo_fallback"
        return tr


# ─── 4. Scene Understanding ───────────────────────────────────────────────────

class SceneUnderstandingTool(BaseTool):
    name = "scene_understanding"
    description = "Classifies scene type and dominant land-cover components. [SIMULATED — requires land-cover model]"
    is_demo = True

    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        context = inputs.get("context", {})
        demo_scenario = context.get("demo_scenario", "demo1")

        if demo_scenario == "demo2":
            components = {"urban_pct": 42.1, "water_pct": 18.3, "vegetation_pct": 28.4,
                          "bare_soil_pct": 7.2, "other_pct": 4.0}
            scene_type = "Mixed urban-riparian"
        else:
            components = {"urban_pct": 31.5, "vegetation_pct": 38.2,
                          "agriculture_pct": 18.1, "water_pct": 9.4, "bare_soil_pct": 2.8}
            scene_type = "Semi-urban riverside landscape"

        img_2024 = demo_imagery.generate_urban_scene("2024", expansion_factor=0.0)
        tr = self._success(
            confidence=0.72,
            result={
                "scene_type": scene_type,
                "dominant_class": max(components, key=components.get).replace("_pct", "").title(),
                "components": components,
                "note": "[SIMULATED] Scene classification requires a land-cover model. Values are scenario-specific.",
            },
            message=f"Scene identified: {scene_type}. [SIMULATED]",
            visual_output=img_2024,
            visual_type="scene_overview",
        )
        tr.is_demo = True
        tr.execution_mode = ExecutionMode.SIMULATED
        tr.input_provenance = InputProvenance.SYNTHETIC_DATA
        tr.algorithm = "demo_scenario_lookup"
        tr.evidence_excludable = True
        return tr


# ─── 5. Object / Region Detection ─────────────────────────────────────────────

class ObjectRegionDetectionTool(BaseTool):
    name = "object_region_detection"
    description = "Identifies regions of interest. [SIMULATED — requires object detection model]"
    is_demo = True

    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        context = inputs.get("context", {})
        target = context.get("target", "built-up areas")
        detections = [
            {"label": "Built-up cluster", "confidence": 0.85, "bbox": [310, 120, 420, 200]},
            {"label": "Water body",        "confidence": 0.90, "bbox": [0, 390, 155, 512]},
            {"label": "River",             "confidence": 0.92, "bbox": [178, 0, 210, 512]},
        ]
        tr = self._success(
            confidence=0.72,
            result={
                "target": target,
                "detections": detections,
                "total_detections": len(detections),
                "note": "[SIMULATED] Bounding boxes are illustrative. Requires real object detection model.",
            },
            message=f"Detected {len(detections)} regions. [SIMULATED]",
        )
        tr.is_demo = True
        tr.execution_mode = ExecutionMode.SIMULATED
        tr.input_provenance = InputProvenance.SYNTHETIC_DATA
        tr.evidence_excludable = True
        return tr


# ─── 6. Land Cover Classification ─────────────────────────────────────────────

class LandCoverClassificationTool(BaseTool):
    name = "land_cover_classification"
    description = "Pixel-level land-cover classification. [SIMULATED — requires spectral bands + classifier]"
    is_demo = True

    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        context = inputs.get("context", {})
        demo_scenario = context.get("demo_scenario", "demo1")

        if demo_scenario in ("demo1", "demo3"):
            before = {"Built-up": 22.3, "Vegetation": 41.5, "Agriculture": 19.8, "Water": 14.2, "Other": 2.2}
            after  = {"Built-up": 31.5, "Vegetation": 34.8, "Agriculture": 19.1, "Water": 12.8, "Other": 1.8}
        else:
            before = {"Built-up": 38.2, "Vegetation": 29.4, "Water": 22.3, "Other": 10.1}
            after  = {"Built-up": 42.1, "Vegetation": 28.4, "Water": 20.7, "Other": 8.8}

        change = {k: round(after[k] - before.get(k, 0), 1) for k in after}
        tr = self._success(
            confidence=0.68,
            result={
                "before_classification": before,
                "after_classification": after,
                "class_changes_pct": change,
                "most_changed_class": max(change, key=lambda k: abs(change[k])),
                "note": "[SIMULATED] Values are scenario-specific. Requires spectral data + classifier.",
            },
            message="Land-cover classification complete. [SIMULATED]",
        )
        tr.is_demo = True
        tr.execution_mode = ExecutionMode.SIMULATED
        tr.input_provenance = InputProvenance.SYNTHETIC_DATA
        tr.evidence_excludable = True
        return tr


# ─── 7. Bi-Temporal Change Detection ──────────────────────────────────────────

class BiTemporalChangeDetectionTool(BaseTool):
    name = "bi_temporal_change_detection"
    description = "Detects pixel-level changes between two dates. Real: abs_diff_otsu_v1."
    is_demo = False

    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        loaded_scenes = inputs.get("loaded_scenes", [])
        if len(loaded_scenes) >= 2:
            prov = getattr(loaded_scenes[0], "input_provenance", InputProvenance.UNKNOWN)
            return self._run_real(loaded_scenes[0].image_b64, loaded_scenes[1].image_b64, provenance=prov)

        image_b64_1 = _extract_scene_b64(inputs, 0)
        image_b64_2 = _extract_scene_b64(inputs, 1)

        if image_b64_1 and image_b64_2:
            return self._run_real(image_b64_1, image_b64_2)
        else:
            return self._run_demo()

    def _run_real(self, image_b64_1: str, image_b64_2: str, provenance: InputProvenance = InputProvenance.USER_UPLOAD) -> ToolResult:
        from backend.tools.change_detector import detect_change
        try:
            cdr = detect_change(image_b64_1, image_b64_2, provenance)

            if cdr.unreliable_registration:
                tr = ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.WARNING,
                    confidence=0.0,
                    result={
                        "unreliable_registration": True,
                        "registration_quality": cdr.registration_quality.value,
                        "registration_method": cdr.registration_method,
                        "changed_area_pct": None,
                        "message": cdr.message,
                    },
                    message="UNRELIABLE_REGISTRATION: Change % not computed.",
                    is_demo=False,
                    execution_mode=ExecutionMode.LIVE_ALGORITHM,
                    input_provenance=InputProvenance.USER_UPLOAD,
                    algorithm=cdr.algorithm,
                    registration_quality=cdr.registration_quality,
                    evidence_excludable=True,
                    warnings=cdr.warnings,
                )
                return tr

            result = {
                "changed_area_pct": cdr.changed_area_pct,
                "changed_pixel_count": cdr.changed_pixel_count,
                "unchanged_pixel_count": cdr.unchanged_pixel_count,
                "total_pixel_count": cdr.total_pixel_count,
                "unreliable_registration": cdr.unreliable_registration,
                "registration_quality": cdr.registration_quality.value,
                "registration_method": cdr.registration_method,
                "registration_error_px": cdr.registration_error_px,
                "otsu_threshold": cdr.otsu_threshold,
                "processed_dimensions": list(cdr.processed_shape),
                "t2_resized": cdr.t2_was_resized,
                "algorithm_note": "Greyscale absolute difference + Otsu threshold. No spectral indices.",
            }
            status = ToolStatus.WARNING if cdr.unreliable_registration else ToolStatus.SUCCESS
            conf = 0.75 if cdr.registration_quality == RegistrationQuality.SUCCESS else 0.50

            tr = ToolResult(
                tool_name=self.name,
                status=status,
                confidence=conf,
                result=result,
                visual_output=cdr.change_mask_b64,
                visual_type="change_map",
                metadata={"heatmap_b64": cdr.change_heatmap_b64} if cdr.change_heatmap_b64 else {},
                message=cdr.message,
                is_demo=False,
                execution_mode=ExecutionMode.LIVE_ALGORITHM,
                input_provenance=provenance,
                algorithm=cdr.algorithm,
                registration_quality=cdr.registration_quality,
                evidence_excludable=cdr.unreliable_registration,
                warnings=cdr.warnings,
            )
            tr.execution_time_ms = cdr.processing_time_ms
            return tr

        except Exception as exc:
            return self._error(f"Real change detection failed: {exc}")

    def _run_demo(self) -> ToolResult:
        time.sleep(0.2)
        change_map = demo_imagery.generate_change_map()
        tr = self._success(
            confidence=0.72,
            result={
                "changed_area_pct": 12.4,
                "unreliable_registration": False,
                "registration_quality": "SIMULATED",
                "note": "[SIMULATED] No real images attached. Attach two images for real analysis.",
                "algorithm_note": "Demo scenario values only.",
            },
            message="Change detection complete. [SIMULATED — no real images]",
            visual_output=change_map,
            visual_type="change_map",
        )
        tr.is_demo = True
        tr.execution_mode = ExecutionMode.SIMULATED
        tr.input_provenance = InputProvenance.SYNTHETIC_DATA
        tr.algorithm = "demo_scenario_lookup"
        tr.evidence_excludable = True
        return tr


# ─── 8. SAR–Optical Fusion ────────────────────────────────────────────────────

class SarOpticalFusionTool(BaseTool):
    name = "sar_optical_fusion"
    description = "Fuses SAR and optical imagery. Currently: SAR_NOT_AVAILABLE."
    is_demo = True

    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        context = inputs.get("context", {})

        # Check if a real SAR image was provided
        sar_b64 = _extract_scene_b64(inputs, 1)
        optical_b64 = _extract_scene_b64(inputs, 0)
        has_sar = sar_b64 is not None and context.get("has_sar_image", False)

        if not has_sar:
            sar_img = demo_imagery.generate_sar_image()
            tr = self._success(
                confidence=0.0,
                result={
                    "cross_modal_status": "SAR_NOT_AVAILABLE",
                    "message": (
                        "No real SAR image was provided for this scene. "
                        "SAR-Optical fusion requires an actual SAR acquisition "
                        "(e.g. Sentinel-1 C-band). "
                        "This result is excluded from evidence scoring."
                    ),
                    "optical_available": optical_b64 is not None,
                    "sar_available": False,
                    "note": "Do not interpret simulated SAR as real cross-modal evidence.",
                },
                message="SAR_NOT_AVAILABLE: No real SAR input provided.",
                visual_output=sar_img,
                visual_type="sar_image",
            )
            tr.is_demo = True
            tr.execution_mode = ExecutionMode.SIMULATED
            tr.input_provenance = InputProvenance.SYNTHETIC_DATA
            tr.evidence_excludable = True
            return tr

        # Future: real SAR processing would go here
        return self._error("Real SAR processing not yet implemented.")


# ─── 9. Spatial Reasoning ─────────────────────────────────────────────────────

class SpatialReasoningTool(BaseTool):
    name = "spatial_reasoning"
    description = "Spatial relationship analysis. [SIMULATED — requires georeference]"
    is_demo = True

    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        tr = self._success(
            confidence=0.60,
            result={
                "spatial_reference": "River (central axis)",
                "target_relation": "Eastern bank (within 500m buffer)",
                "note": "[SIMULATED] Requires real georeferenced imagery. Values are illustrative.",
            },
            message="Spatial analysis complete. [SIMULATED]",
        )
        tr.is_demo = True
        tr.execution_mode = ExecutionMode.SIMULATED
        tr.input_provenance = InputProvenance.SYNTHETIC_DATA
        tr.evidence_excludable = True
        return tr


# ─── 10. Evidence Comparison ──────────────────────────────────────────────────

class EvidenceComparisonTool(BaseTool):
    name = "evidence_comparison"
    description = "Compares outputs from multiple tools using explainable evidence strength scoring."
    is_demo = False

    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        from backend.tools.evidence import compute_evidence_strength
        context = inputs.get("context", {})
        tool_results = context.get("tool_results", [])

        ev = compute_evidence_strength(tool_results)

        conflict = any(r.get("result", {}).get("agreement") is False for r in tool_results)

        tr = self._success(
            confidence=ev.evidence_strength,
            result={
                "evidence_strength": ev.evidence_strength,
                "confidence_level": ev.confidence_level,
                "low_evidence": ev.low_evidence,
                "secondary_evidence_status": ev.secondary_evidence_status.value if ev.secondary_evidence_status else None,
                "secondary_evidence_reason": ev.secondary_evidence_reason,
                "breakdown": ev.breakdown,
                "formula": ev.formula,
                "interpretation": ev.interpretation,
                "conflict_detected": conflict,
                "agreement": not conflict,
            },
            message=f"Evidence strength: {ev.evidence_strength:.2f} — {ev.interpretation}",
        )
        tr.is_demo = False
        tr.execution_mode = ExecutionMode.LIVE_ALGORITHM
        tr.algorithm = "evidence_strength_calculator_v1"
        return tr


# ─── Confidence Check ─────────────────────────────────────────────────────────

class ConfidenceCheckTool(BaseTool):
    name = "confidence_check"
    description = "Aggregates evidence and checks whether re-analysis is warranted."
    is_demo = False

    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        from backend.tools.evidence import compute_evidence_strength, LOW_EVIDENCE_THRESHOLD
        context = inputs.get("context", {})
        tool_results = context.get("tool_results", [])

        ev = compute_evidence_strength(tool_results)

        needs_reanalysis = ev.low_evidence
        level = ev.confidence_level

        tr = self._success(
            confidence=ev.evidence_strength,
            result={
                "evidence_strength": ev.evidence_strength,
                "confidence_level": level,
                "threshold": LOW_EVIDENCE_THRESHOLD,
                "needs_reanalysis": needs_reanalysis,
                "secondary_evidence_status": ev.secondary_evidence_status.value if ev.secondary_evidence_status else None,
                "interpretation": ev.interpretation,
                "formula": ev.formula,
            },
            message=(
                f"Evidence strength: {ev.evidence_strength:.2f} ({level.upper()}). "
                + (
                    f"Secondary evidence: {ev.secondary_evidence_status.value}."
                    if ev.secondary_evidence_status
                    else ""
                )
            ),
        )
        tr.is_demo = False
        tr.execution_mode = ExecutionMode.LIVE_ALGORITHM
        tr.algorithm = "evidence_strength_calculator_v1"
        return tr


# ─── Answer Synthesis ─────────────────────────────────────────────────────────

class AnswerSynthesisTool(BaseTool):
    name = "answer_synthesis"
    description = "Synthesises tool results into a final answer grounded in actual evidence."
    is_demo = True

    ANSWERS = {
        "demo1": (
            "Based on bi-temporal analysis of the Sentinel-2 imagery (2024–2026), "
            "built-up land cover increased by approximately 9.2 percentage points within "
            "the selected region. The largest detected changes are concentrated on the "
            "eastern bank of the river, within a 300-metre buffer zone. Vegetation cover "
            "correspondingly decreased by 6.7 percentage points."
        ),
        "demo2": (
            "Cross-modal analysis identifies built-up regions covering approximately 42% of the scene. "
            "Note: SAR imagery was not available for this session — SAR fusion was not performed. "
            "Classification is based on optical imagery only."
        ),
        "demo3": (
            "The input optical image contained significant cloud contamination (38% coverage). "
            "The agent automatically triggered cloud reconstruction before proceeding. "
            "Post-reconstruction analysis identifies built-up expansion of approximately 11% "
            "between the two dates. Results in areas of high cloud coverage should be interpreted with caution."
        ),
    }

    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        context = inputs.get("context", {})
        demo_scenario = context.get("demo_scenario", "demo1")
        tool_results = context.get("tool_results", [])

        # Prefer real change detection result if available
        real_change = None
        for r in tool_results:
            if (r.get("tool_name") == "bi_temporal_change_detection"
                    and not r.get("evidence_excludable")
                    and r.get("result", {}).get("changed_area_pct") is not None):
                real_change = r["result"]["changed_area_pct"]
                break

        if real_change is not None:
            answer = (
                f"Real change detection analysis (algorithm: abs_diff_otsu_v1) found "
                f"{real_change:.1f}% of the analysed area changed between the two input images. "
                f"Registration was performed using ECC. "
                f"Note: this is pixel-intensity change — semantic interpretation requires a land-cover model."
            )
        else:
            answer = self.ANSWERS.get(demo_scenario, self.ANSWERS["demo1"])

        evidence = []
        for r in tool_results:
            name = r.get("tool_name", "")
            if name not in ("image_validation", "confidence_check", "answer_synthesis", "evidence_comparison"):
                mode = r.get("execution_mode", "SIMULATED")
                label = "✓ LIVE" if mode == ExecutionMode.LIVE_ALGORITHM else "○ DEMO"
                evidence.append(f"{label} — {name.replace('_', ' ').title()}")

        tr = self._success(
            confidence=0.80,
            result={
                "final_answer": answer,
                "evidence_points": evidence,
                "query_answered": True,
                "real_change_pct_used": real_change,
            },
            message="Final answer generated.",
        )
        tr.execution_mode = ExecutionMode.SIMULATED
        tr.input_provenance = InputProvenance.SYNTHETIC_DATA
        return tr


# ─── Tool Registry ─────────────────────────────────────────────────────────────

TOOL_REGISTRY: Dict[str, BaseTool] = {
    "image_validation":           ImageValidationTool(),
    "cloud_detection":            CloudDetectionTool(),
    "cloud_reconstruction":       CloudReconstructionTool(),
    "scene_understanding":        SceneUnderstandingTool(),
    "object_region_detection":    ObjectRegionDetectionTool(),
    "land_cover_classification":  LandCoverClassificationTool(),
    "bi_temporal_change_detection": BiTemporalChangeDetectionTool(),
    "sar_optical_fusion":         SarOpticalFusionTool(),
    "spatial_reasoning":          SpatialReasoningTool(),
    "evidence_comparison":        EvidenceComparisonTool(),
    "confidence_check":           ConfidenceCheckTool(),
    "answer_synthesis":           AnswerSynthesisTool(),
}


def get_tool(name: str) -> BaseTool:
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        raise ValueError(f"Unknown tool: {name}")
    return tool
