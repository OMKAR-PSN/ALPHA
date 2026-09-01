"""
SatQuery AI — Cloud Detector Tests
Tests that the real cloud detector produces scientifically consistent results
on known synthetic inputs. Synthetic images are used here for test repeatability —
they are NOT presented as remote-sensing capability evidence.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from backend.tools.cloud_detector import (
    detect_clouds_from_array,
    detect_clouds_rgb,
    BRIGHTNESS_THRESHOLD,
    WHITENESS_THRESHOLD,
    RECON_THRESHOLD,
)
from backend.schemas.provenance import ExecutionMode, InputProvenance


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_white_image(h=64, w=64):
    """All-white image → should be close to 100% cloud."""
    return np.full((h, w, 3), 255, dtype=np.uint8)


def make_black_image(h=64, w=64):
    """All-black image → 0% cloud."""
    return np.zeros((h, w, 3), dtype=np.uint8)


def make_green_image(h=64, w=64):
    """Vivid green → low whiteness, should be ~0% cloud."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :, 1] = 200   # strong green channel
    return img


def make_patched_image(h=64, w=64, patch_fraction=0.25):
    """
    Green background with a white cloud patch in the top-left corner.
    Known cloud area fraction is 'patch_fraction'.
    """
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :, 1] = 180   # green background (low brightness, vivid)
    ph = int(h * patch_fraction ** 0.5)
    pw = int(w * patch_fraction ** 0.5)
    img[:ph, :pw, :] = 240  # bright-white patch
    return img, ph * pw / (h * w)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCloudDetectorBasicResults:

    def test_white_image_near_100_percent(self):
        """Pure white → essentially all cloud pixels."""
        result = detect_clouds_from_array(make_white_image())
        assert result.cloud_percentage > 90.0, (
            f"Expected >90% cloud for white image, got {result.cloud_percentage}"
        )

    def test_black_image_zero_percent(self):
        """Pure black → no cloud pixels."""
        result = detect_clouds_from_array(make_black_image())
        assert result.cloud_percentage < 5.0, (
            f"Expected <5% cloud for black image, got {result.cloud_percentage}"
        )

    def test_green_image_zero_percent(self):
        """Vivid green → not cloud (high saturation, not white)."""
        result = detect_clouds_from_array(make_green_image())
        assert result.cloud_percentage < 10.0, (
            f"Expected <10% cloud for green image, got {result.cloud_percentage}"
        )

    def test_patched_image_within_tolerance(self):
        """
        Known patch fraction should be within ±15% of detected cloud_percentage.
        The ±15% tolerance accounts for morphological filtering edge effects.
        """
        img, true_fraction = make_patched_image(h=128, w=128, patch_fraction=0.25)
        result = detect_clouds_from_array(img)
        detected = result.cloud_percentage / 100.0
        assert abs(detected - true_fraction) < 0.15, (
            f"Patch fraction {true_fraction:.2f}, detected {detected:.2f} — "
            f"difference exceeds ±0.15 tolerance"
        )


class TestCloudDetectorOutputSchema:

    def test_result_has_algorithm_field(self):
        result = detect_clouds_from_array(make_white_image())
        assert result.algorithm == "rgb_cloud_detector_v1"

    def test_result_has_live_algorithm_mode(self):
        result = detect_clouds_from_array(make_white_image())
        assert result.execution_mode == ExecutionMode.LIVE_ALGORITHM

    def test_mask_dimensions_match_input(self):
        """Cloud mask must have the same HxW as the input image."""
        import base64, io
        from PIL import Image

        img = make_patched_image(h=80, w=100)[0]
        result = detect_clouds_from_array(img)
        # Decode mask
        mask_bytes = base64.b64decode(result.cloud_mask_b64)
        mask_pil = Image.open(io.BytesIO(mask_bytes))
        assert mask_pil.size == (100, 80), (
            f"Expected mask size (100, 80), got {mask_pil.size}"
        )

    def test_pixel_counts_sum_to_total(self):
        img = make_patched_image(h=64, w=64)[0]
        result = detect_clouds_from_array(img)
        assert result.cloud_pixel_count + result.clear_pixel_count == result.total_pixel_count

    def test_cloud_pct_consistent_with_pixel_counts(self):
        img = make_white_image(h=64, w=64)
        result = detect_clouds_from_array(img)
        expected_pct = result.cloud_pixel_count / result.total_pixel_count * 100
        assert abs(result.cloud_percentage - expected_pct) < 0.01

    def test_limitations_field_is_non_empty(self):
        """Limitations must always be reported — never suppressed."""
        result = detect_clouds_from_array(make_green_image())
        assert len(result.limitations) >= 1

    def test_no_nir_or_ndvi_in_result(self):
        """rgb_cloud_detector_v1 must NOT claim NIR-based features."""
        result = detect_clouds_from_array(make_white_image())
        result_dict = result.__dict__
        result_str = str(result_dict).lower()
        # None of the RGB-only detection result fields should mention NIR/NDVI/NDWI
        assert "ndvi" not in result_str
        assert "ndwi" not in result_str
        assert "near-infrared" not in result_str


class TestCloudDetectorReconstruction:

    def test_requires_reconstruction_when_above_threshold(self):
        """High cloud coverage should set requires_reconstruction=True."""
        result = detect_clouds_from_array(make_white_image())
        if result.cloud_percentage >= RECON_THRESHOLD:
            assert result.requires_reconstruction is True

    def test_no_reconstruction_when_clear(self):
        """Clear image should not trigger reconstruction."""
        result = detect_clouds_from_array(make_black_image())
        assert result.requires_reconstruction is False


class TestCloudDetectorErrorHandling:

    def test_invalid_base64_raises_value_error(self):
        with pytest.raises(ValueError, match="Failed to decode image"):
            detect_clouds_rgb("this_is_not_valid_base64_!!!")

    def test_synthetic_data_provenance_preserved(self):
        result = detect_clouds_from_array(
            make_white_image(),
            input_provenance=InputProvenance.SYNTHETIC_DATA,
        )
        assert result.input_provenance == InputProvenance.SYNTHETIC_DATA


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
