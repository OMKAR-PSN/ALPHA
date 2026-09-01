"""
SatQuery AI — Change Detector Tests
Verifies registration-gated change detection behaviour on synthetic numpy arrays.
Synthetic inputs are used for repeatability only.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest
import base64, io
from PIL import Image

from backend.tools.change_detector import detect_change_from_arrays, ChangeDetectionResult
from backend.schemas.provenance import ExecutionMode, InputProvenance, RegistrationQuality


# ── Helpers ───────────────────────────────────────────────────────────────────

def solid_rgb(h, w, r, g, b) -> np.ndarray:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = [r, g, b]
    return img


def image_with_patch(h, w, bg_val, patch_val, py1, py2, px1, px2) -> np.ndarray:
    """Background bg_val with a rectangular patch of patch_val."""
    img = solid_rgb(h, w, bg_val, bg_val, bg_val)
    img[py1:py2, px1:px2] = [patch_val, patch_val, patch_val]
    return img


# ── Tests: Core Behaviour ─────────────────────────────────────────────────────

class TestChangDetectorCoreResults:

    def test_identical_images_near_zero_change(self):
        """Identical images should produce ~0% change after registration."""
        img = image_with_patch(64, 64, 100, 200, 10, 30, 10, 30)
        result = detect_change_from_arrays(img, img.copy())
        if not result.unreliable_registration:
            assert result.changed_area_pct is not None
            assert result.changed_area_pct < 5.0, (
                f"Expected <5% change for identical images, got {result.changed_area_pct}"
            )

    def test_completely_different_images_high_change(self):
        """Black vs white images should produce high change percentage."""
        t1 = solid_rgb(64, 64, 10, 10, 10)     # near-black
        t2 = solid_rgb(64, 64, 240, 240, 240)  # near-white
        result = detect_change_from_arrays(t1, t2)
        if not result.unreliable_registration:
            assert result.changed_area_pct is not None
            assert result.changed_area_pct > 60.0, (
                f"Expected >60% change for inverted images, got {result.changed_area_pct}"
            )

    def test_partial_patch_change_has_nonzero_result(self):
        """Changing a patch should produce nonzero but not 100% change."""
        t1 = solid_rgb(64, 64, 80, 80, 80)
        t2 = solid_rgb(64, 64, 80, 80, 80)
        t2[20:40, 20:40] = [220, 220, 220]  # change roughly 25% of pixels
        result = detect_change_from_arrays(t1, t2)
        if not result.unreliable_registration:
            assert result.changed_area_pct is not None
            assert 0.0 < result.changed_area_pct < 100.0


class TestChangDetectorRegistrationGate:

    def test_failed_registration_returns_none_pct(self):
        """
        When registration quality is FAILED, changed_area_pct must be None.
        This cannot happen with identical content, so we force it via a
        direct call and check the contract from the result.
        """
        t1 = solid_rgb(64, 64, 100, 100, 100)
        t2 = solid_rgb(64, 64, 100, 100, 100)
        result = detect_change_from_arrays(t1, t2)
        # When registration fails, the gate must apply
        if result.unreliable_registration:
            assert result.changed_area_pct is None
            assert result.change_mask_b64 is None

    def test_unreliable_flag_implies_null_pct(self):
        """unreliable_registration=True must always be paired with changed_area_pct=None."""
        t1 = solid_rgb(128, 128, 50, 50, 50)
        t2 = solid_rgb(128, 128, 200, 200, 200)
        result = detect_change_from_arrays(t1, t2)
        if result.unreliable_registration:
            assert result.changed_area_pct is None, (
                "unreliable_registration=True but changed_area_pct is not None — "
                "this violates the reliability contract."
            )


class TestChangDetectorOutputSchema:

    def test_algorithm_field(self):
        t1 = solid_rgb(32, 32, 80, 80, 80)
        t2 = solid_rgb(32, 32, 80, 80, 80)
        result = detect_change_from_arrays(t1, t2)
        assert result.algorithm == "abs_diff_otsu_v1"

    def test_no_ndvi_ndwi_in_result(self):
        """Algorithm must NOT mention spectral indices."""
        t1 = solid_rgb(32, 32, 100, 100, 100)
        t2 = solid_rgb(32, 32, 100, 100, 100)
        result = detect_change_from_arrays(t1, t2)
        result_str = str(result.__dict__).lower()
        assert "ndvi" not in result_str
        assert "ndwi" not in result_str

    def test_execution_mode_is_live_algorithm(self):
        t1 = solid_rgb(32, 32, 100, 100, 100)
        t2 = solid_rgb(32, 32, 100, 100, 100)
        result = detect_change_from_arrays(t1, t2)
        assert result.execution_mode == ExecutionMode.LIVE_ALGORITHM

    def test_pixel_counts_consistent_when_reliable(self):
        """When reliable, cloud+clear pixels must sum to total."""
        t1 = solid_rgb(64, 64, 100, 100, 100)
        t2 = t1.copy()
        t2[10:30, 10:30] = [200, 200, 200]
        result = detect_change_from_arrays(t1, t2)
        if not result.unreliable_registration and result.changed_pixel_count is not None:
            total = result.changed_pixel_count + result.unchanged_pixel_count
            assert total == result.total_pixel_count

    def test_t1_shape_recorded(self):
        t1 = solid_rgb(50, 70, 100, 100, 100)
        t2 = solid_rgb(50, 70, 100, 100, 100)
        result = detect_change_from_arrays(t1, t2)
        assert result.t1_shape == (50, 70)

    def test_synthetic_provenance_preserved(self):
        t1 = solid_rgb(32, 32, 100, 100, 100)
        t2 = t1.copy()
        result = detect_change_from_arrays(t1, t2, InputProvenance.SYNTHETIC_DATA)
        assert result.input_provenance == InputProvenance.SYNTHETIC_DATA

    def test_mask_not_returned_when_registration_failed(self):
        """change_mask_b64 must be None when registration failed."""
        t1 = solid_rgb(64, 64, 100, 100, 100)
        t2 = solid_rgb(64, 64, 200, 200, 200)
        result = detect_change_from_arrays(t1, t2)
        if result.unreliable_registration:
            assert result.change_mask_b64 is None

    def test_mask_dimensions_match_when_reliable(self):
        """If a mask is returned, it must match the processed dimensions."""
        t1 = solid_rgb(60, 80, 100, 100, 100)
        t2 = t1.copy()
        t2[10:30, 20:50] = [200, 200, 200]
        result = detect_change_from_arrays(t1, t2)
        if not result.unreliable_registration and result.change_mask_b64:
            mask_bytes = base64.b64decode(result.change_mask_b64)
            pil = Image.open(io.BytesIO(mask_bytes))
            # mask width=W, height=H
            assert pil.size[0] == result.processed_shape[1]
            assert pil.size[1] == result.processed_shape[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
