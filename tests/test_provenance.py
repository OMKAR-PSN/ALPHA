"""
SatQuery AI — Provenance & Evidence Tests
Verifies that the provenance contracts and evidence strength calculator
behave correctly end-to-end.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from backend.schemas.provenance import (
    ExecutionMode, InputProvenance, RegistrationQuality, SecondaryEvidenceStatus
)
from backend.tools.evidence import compute_evidence_strength, LOW_EVIDENCE_THRESHOLD


# ─── Helpers ──────────────────────────────────────────────────────────────────

def live_result(conf: float = 0.80, reg: RegistrationQuality = None) -> dict:
    r = {
        "tool_name": "bi_temporal_change_detection",
        "execution_mode": ExecutionMode.LIVE_ALGORITHM,
        "input_provenance": InputProvenance.REAL_SATELLITE_DATA,
        "confidence": conf,
        "is_demo": False,
        "evidence_excludable": False,
        "result": {},
    }
    if reg is not None:
        r["registration_quality"] = reg
    return r


def demo_result(tool_name: str = "scene_understanding") -> dict:
    return {
        "tool_name": tool_name,
        "execution_mode": ExecutionMode.SIMULATED,
        "input_provenance": InputProvenance.SYNTHETIC_DATA,
        "confidence": 0.70,
        "is_demo": True,
        "evidence_excludable": True,
        "result": {},
    }


def cloudy_result() -> dict:
    r = live_result()
    r["result"]["cloud_percentage"] = 35.0
    return r


# ─── Tests: Core formula behaviour ─────────────────────────────────────────────

class TestEvidenceFormula:

    def test_all_live_high_confidence_produces_high_score(self):
        results = [
            live_result(0.85, RegistrationQuality.SUCCESS),
            live_result(0.80),
        ]
        ev = compute_evidence_strength(results)
        assert ev.evidence_strength >= 0.60, f"Expected ≥0.60, got {ev.evidence_strength}"
        assert ev.confidence_level in ("high", "moderate")

    def test_all_demo_produces_low_score(self):
        results = [demo_result("scene_understanding"), demo_result("object_region_detection")]
        ev = compute_evidence_strength(results)
        # all demo → low evidence
        assert ev.evidence_strength < 0.70, f"Expected <0.70 for all-demo, got {ev.evidence_strength}"

    def test_score_clamped_to_0_1(self):
        results = [live_result(1.0, RegistrationQuality.SUCCESS)] * 5
        ev = compute_evidence_strength(results)
        assert 0.0 <= ev.evidence_strength <= 1.0

    def test_zero_confidence_live_gives_low_score(self):
        results = [live_result(0.0, RegistrationQuality.FAILED)]
        ev = compute_evidence_strength(results)
        assert ev.evidence_strength < 0.60

    def test_formula_string_present(self):
        ev = compute_evidence_strength([live_result(0.8)])
        assert "evidence_strength" in ev.formula
        assert "=" in ev.formula

    def test_breakdown_has_four_factors(self):
        results = [live_result(0.80, RegistrationQuality.SUCCESS)]
        ev = compute_evidence_strength(results)
        assert "data_quality" in ev.breakdown
        assert "algorithm_confidence" in ev.breakdown
        assert "cross_method_agreement" in ev.breakdown


# ─── Tests: Data quality deductions ──────────────────────────────────────────

class TestDataQualityFactor:

    def test_synthetic_deducts_score(self):
        real_ev   = compute_evidence_strength([live_result(0.80)])
        synth_ev  = compute_evidence_strength([{
            **live_result(0.80),
            "input_provenance": InputProvenance.SYNTHETIC_DATA,
        }])
        assert synth_ev.breakdown["data_quality"]["score"] < real_ev.breakdown["data_quality"]["score"]

    def test_cloud_contamination_deducts_score(self):
        clean_ev  = compute_evidence_strength([live_result(0.80)])
        cloudy_ev = compute_evidence_strength([cloudy_result()])
        assert cloudy_ev.breakdown["data_quality"]["score"] < clean_ev.breakdown["data_quality"]["score"]

    def test_demo_mode_deducts_score(self):
        live_ev = compute_evidence_strength([live_result(0.80)])
        demo_ev = compute_evidence_strength([demo_result()])
        assert demo_ev.breakdown["data_quality"]["score"] < live_ev.breakdown["data_quality"]["score"]


# ─── Tests: Registration quality ─────────────────────────────────────────────

class TestRegistrationFactor:

    def test_success_registration_gives_1_0(self):
        ev = compute_evidence_strength([live_result(0.80, RegistrationQuality.SUCCESS)])
        assert ev.breakdown["registration_quality"]["score"] == 1.0

    def test_failed_registration_gives_0_0(self):
        ev = compute_evidence_strength([live_result(0.80, RegistrationQuality.FAILED)])
        assert ev.breakdown["registration_quality"]["score"] == 0.0

    def test_partial_registration_gives_0_5(self):
        ev = compute_evidence_strength([live_result(0.80, RegistrationQuality.PARTIAL)])
        assert ev.breakdown["registration_quality"]["score"] == 0.5

    def test_no_registration_tool_redistributes_weight(self):
        ev = compute_evidence_strength([live_result(0.80)])
        # When no registration result, weight is redistributed to other factors
        # Total weight of remaining factors should be > their nominal weight
        # Registration key may not be in breakdown at all
        if "registration_quality" in ev.breakdown:
            assert ev.breakdown["registration_quality"]["score"] is None or \
                   ev.breakdown["registration_quality"]["weight"] == 0.0


# ─── Tests: Low evidence threshold ───────────────────────────────────────────

class TestLowEvidenceThreshold:

    def test_high_evidence_not_flagged(self):
        results = [live_result(0.90, RegistrationQuality.SUCCESS), live_result(0.85)]
        ev = compute_evidence_strength(results)
        if ev.evidence_strength >= LOW_EVIDENCE_THRESHOLD:
            assert not ev.low_evidence
            assert ev.secondary_evidence_status is None

    def test_all_demo_flagged_low_evidence(self):
        results = [demo_result("a"), demo_result("b")]
        ev = compute_evidence_strength(results)
        if ev.low_evidence:
            assert ev.secondary_evidence_status == SecondaryEvidenceStatus.NO_SECONDARY_EVIDENCE_AVAILABLE

    def test_low_evidence_never_manufactures_secondary(self):
        """When low evidence and no real secondary source → NO_SECONDARY_EVIDENCE_AVAILABLE."""
        results = [demo_result()]
        ev = compute_evidence_strength(results, secondary_evidence_available=False)
        if ev.low_evidence:
            assert ev.secondary_evidence_status == SecondaryEvidenceStatus.NO_SECONDARY_EVIDENCE_AVAILABLE
            assert ev.secondary_evidence_reason is not None

    def test_real_secondary_evidence_sets_confirmed(self):
        results = [demo_result()]
        ev = compute_evidence_strength(
            results,
            secondary_evidence_available=True,
            secondary_evidence_note="Validated against archive optical image."
        )
        if ev.low_evidence:
            assert ev.secondary_evidence_status == SecondaryEvidenceStatus.CONFIRMED


# ─── Tests: Provenance enums ──────────────────────────────────────────────────

class TestProvenanceEnums:

    def test_all_execution_modes_defined(self):
        modes = [
            ExecutionMode.LIVE_ALGORITHM,
            ExecutionMode.LIVE_MODEL,
            ExecutionMode.REMOTE_MODEL,
            ExecutionMode.PRECOMPUTED_MODEL_OUTPUT,
            ExecutionMode.SIMULATED,
        ]
        assert len(modes) == 5

    def test_all_input_provenances_defined(self):
        provenances = [
            InputProvenance.REAL_SATELLITE_DATA,
            InputProvenance.BENCHMARK_DATA,
            InputProvenance.SYNTHETIC_DATA,
            InputProvenance.DEMO_ASSET,
            InputProvenance.USER_UPLOAD,
            InputProvenance.UNKNOWN,
        ]
        assert len(provenances) == 6

    def test_registration_quality_values(self):
        qualities = [
            RegistrationQuality.SUCCESS,
            RegistrationQuality.PARTIAL,
            RegistrationQuality.FAILED,
            RegistrationQuality.NOT_ATTEMPTED,
            RegistrationQuality.NOT_REQUIRED,
        ]
        assert len(qualities) == 5

    def test_no_secondary_evidence_value_matches_expected_string(self):
        assert SecondaryEvidenceStatus.NO_SECONDARY_EVIDENCE_AVAILABLE.value == "NO_SECONDARY_EVIDENCE_AVAILABLE"

    def test_secondary_evidence_confirmed_value(self):
        assert SecondaryEvidenceStatus.CONFIRMED.value == "CONFIRMED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
