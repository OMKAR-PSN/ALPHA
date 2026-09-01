"""
SatQuery AI — Evidence Strength Calculator

Computes an explainable Evidence Strength Score (0–1) from the results
of the specialist-tool pipeline.

This is NOT probabilistic confidence. It is a structured score built
from verifiable factors, with each factor documented.

Formula (documented):
  evidence_strength =
      0.25 * data_quality_score
    + 0.30 * algorithm_confidence
    + 0.25 * registration_quality_score
    + 0.20 * cross_method_agreement

Factor definitions:
  data_quality_score:
    - Start at 1.0
    - Deduct 0.3 if any input has SYNTHETIC_DATA provenance
    - Deduct 0.2 if any input is UNKNOWN provenance
    - Deduct 0.3 if cloud_percentage >= 20 (cloud contamination)
    - Deduct 0.2 if any tool has is_demo=True
    - Clamp to [0, 1]

  algorithm_confidence:
    - Mean of tool confidence scores WHERE execution_mode == LIVE_ALGORITHM
    - If no LIVE_ALGORITHM tools: 0.0 (all simulated)

  registration_quality_score:
    - SUCCESS  → 1.0
    - PARTIAL  → 0.5
    - FAILED   → 0.0  (change result was blocked)
    - NOT_ATTEMPTED / NOT_REQUIRED → excluded from formula (weight redistributed)

  cross_method_agreement:
    - All tools agree (no conflict) → 1.0
    - One conflict → 0.5
    - Multiple conflicts → 0.0
    - Only one LIVE_ALGORITHM tool → 0.5 (single-method, no cross-check possible)

Secondary evidence:
  The evidence strength does NOT trigger a secondary analysis unless
  a genuinely independent second source exists.
  If evidence_strength < LOW_EVIDENCE_THRESHOLD:
    → emit LOW_EVIDENCE event
    → check for real independent secondary method
    → if none: return NO_SECONDARY_EVIDENCE_AVAILABLE
    → NEVER manufacture a secondary analysis to trigger the demo

Interpretation labels:
  0.80–1.00: High evidence — result is likely reliable
  0.60–0.79: Moderate evidence — minor caveats
  0.40–0.59: Low evidence — results should be treated with caution
  0.00–0.39: Very low evidence — result is not suitable for reporting
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.schemas.provenance import (
    ExecutionMode, InputProvenance, RegistrationQuality, SecondaryEvidenceStatus
)


# ── Constants ─────────────────────────────────────────────────────────────────

WEIGHTS = {
    "data_quality":         0.25,
    "algorithm_confidence": 0.30,
    "registration_quality": 0.25,
    "cross_method_agreement": 0.20,
}
LOW_EVIDENCE_THRESHOLD = 0.55


# ── Result data class ─────────────────────────────────────────────────────────

@dataclass
class EvidenceStrengthResult:
    evidence_strength: float
    confidence_level: str           # "high" | "moderate" | "low" | "very_low"
    breakdown: Dict[str, Dict]      # factor → {score, reason, weight}
    formula: str
    low_evidence: bool
    secondary_evidence_status: Optional[SecondaryEvidenceStatus]
    secondary_evidence_reason: Optional[str]
    interpretation: str
    warnings: list = field(default_factory=list)


def _interpret(score: float) -> str:
    if score >= 0.80:
        return "High evidence — result is likely reliable."
    elif score >= 0.60:
        return "Moderate evidence — minor caveats apply."
    elif score >= 0.40:
        return "Low evidence — results should be treated with caution."
    else:
        return "Very low evidence — result is not suitable for authoritative reporting."


def _confidence_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    elif score >= 0.55:
        return "moderate"
    elif score >= 0.35:
        return "low"
    return "very_low"


# ── Factor calculators ────────────────────────────────────────────────────────

def _data_quality_factor(tool_results: List[Dict]) -> Dict:
    score = 1.0
    reasons = []

    # Check provenance across all results
    provenances = [r.get("input_provenance") for r in tool_results if r.get("input_provenance")]
    has_synthetic = any(p == InputProvenance.SYNTHETIC_DATA for p in provenances)
    has_unknown   = any(p == InputProvenance.UNKNOWN for p in provenances)

    if has_synthetic:
        score -= 0.30
        reasons.append("Synthetic input data (-0.30)")
    if has_unknown:
        score -= 0.20
        reasons.append("Unknown input provenance (-0.20)")

    # Check cloud contamination
    for r in tool_results:
        result_data = r.get("result", {})
        cloud_pct = result_data.get("cloud_percentage") or result_data.get("cloud_coverage_pct")
        if cloud_pct is not None and cloud_pct >= 20.0:
            score -= 0.30
            reasons.append(f"Cloud contamination {cloud_pct:.1f}% ≥ 20% threshold (-0.30)")
            break

    # Check if any tool is demo-mode
    any_demo = any(r.get("is_demo", True) for r in tool_results)
    if any_demo:
        score -= 0.20
        reasons.append("Some tools ran in demo/simulated mode (-0.20)")

    score = max(0.0, min(1.0, score))
    if not reasons:
        reasons.append("All inputs have verified provenance, no cloud contamination, live algorithms.")

    return {
        "score": round(score, 3),
        "reason": " | ".join(reasons),
        "weight": WEIGHTS["data_quality"],
    }


def _algorithm_confidence_factor(tool_results: List[Dict]) -> Dict:
    live_confs = [
        r.get("confidence", 0.0)
        for r in tool_results
        if r.get("execution_mode") == ExecutionMode.LIVE_ALGORITHM
        and not r.get("evidence_excludable", False)
        and r.get("confidence") is not None
    ]

    if not live_confs:
        return {
            "score": 0.0,
            "reason": "No LIVE_ALGORITHM tool results available — all tools ran in simulated mode.",
            "weight": WEIGHTS["algorithm_confidence"],
        }

    score = round(sum(live_confs) / len(live_confs), 3)
    return {
        "score": score,
        "reason": (
            f"Mean confidence across {len(live_confs)} LIVE_ALGORITHM tool(s): {score:.3f}. "
            f"Excludes simulated and excluded results."
        ),
        "weight": WEIGHTS["algorithm_confidence"],
    }


def _registration_factor(tool_results: List[Dict]) -> Optional[Dict]:
    """
    Returns None if no registration result exists (weight redistributed).
    """
    for r in tool_results:
        reg_quality = r.get("registration_quality")
        if reg_quality is None:
            continue
        if reg_quality == RegistrationQuality.SUCCESS:
            return {
                "score": 1.0,
                "reason": "ECC registration succeeded within strict error threshold.",
                "weight": WEIGHTS["registration_quality"],
            }
        elif reg_quality == RegistrationQuality.PARTIAL:
            return {
                "score": 0.5,
                "reason": "Registration converged but error exceeded strict threshold — partial quality.",
                "weight": WEIGHTS["registration_quality"],
            }
        elif reg_quality == RegistrationQuality.FAILED:
            return {
                "score": 0.0,
                "reason": "Registration FAILED — change detection result excluded from evidence.",
                "weight": WEIGHTS["registration_quality"],
            }
        elif reg_quality in (RegistrationQuality.NOT_ATTEMPTED, RegistrationQuality.NOT_REQUIRED):
            return {
                "score": None,  # weight redistributed
                "reason": "Registration not applicable for this analysis type.",
                "weight": 0.0,  # excluded from sum
            }
    # No registration tool ran
    return None


def _cross_method_agreement_factor(tool_results: List[Dict]) -> Dict:
    conflicts = sum(
        1 for r in tool_results
        if r.get("result", {}).get("agreement") is False
    )
    live_count = sum(
        1 for r in tool_results
        if r.get("execution_mode") == ExecutionMode.LIVE_ALGORITHM
    )

    if conflicts >= 2:
        score = 0.0
        reason = f"Multiple conflicts ({conflicts}) detected between tools."
    elif conflicts == 1:
        score = 0.5
        reason = "One conflict detected between tools."
    elif live_count <= 1:
        score = 0.5
        reason = "Only one LIVE_ALGORITHM tool — no cross-method check possible."
    else:
        score = 1.0
        reason = f"All {live_count} LIVE_ALGORITHM tools agree — no conflicts."

    return {
        "score": round(score, 3),
        "reason": reason,
        "weight": WEIGHTS["cross_method_agreement"],
    }


# ── Main function ─────────────────────────────────────────────────────────────

def compute_evidence_strength(
    tool_results: List[Dict],
    secondary_evidence_available: bool = False,
    secondary_evidence_note: Optional[str] = None,
) -> EvidenceStrengthResult:
    """
    Compute explainable Evidence Strength Score from tool results.

    Args:
        tool_results:  List of ToolResult.model_dump() dicts from the pipeline.
        secondary_evidence_available: True only if a real independent
            evidence source was actually checked.
        secondary_evidence_note: Human-readable description of what secondary
            evidence was checked (or why none was available).

    Returns:
        EvidenceStrengthResult with full breakdown and provenance metadata.
    """
    # ── Compute factors ───────────────────────────────────────────────────────
    data_q    = _data_quality_factor(tool_results)
    algo_conf = _algorithm_confidence_factor(tool_results)
    reg_q     = _registration_factor(tool_results)
    agree_q   = _cross_method_agreement_factor(tool_results)

    # ── Redistribute registration weight if not applicable ────────────────────
    if reg_q is None or reg_q.get("score") is None:
        # Spread the registration weight across remaining three factors
        extra = WEIGHTS["registration_quality"] / 3.0
        w_data  = WEIGHTS["data_quality"]         + extra
        w_algo  = WEIGHTS["algorithm_confidence"] + extra
        w_agree = WEIGHTS["cross_method_agreement"] + extra
        reg_contribution = 0.0
    else:
        w_data  = WEIGHTS["data_quality"]
        w_algo  = WEIGHTS["algorithm_confidence"]
        w_agree = WEIGHTS["cross_method_agreement"]
        reg_contribution = reg_q["score"] * WEIGHTS["registration_quality"]

    # ── Weighted sum ──────────────────────────────────────────────────────────
    evidence_strength = round(
        data_q["score"] * w_data
        + algo_conf["score"] * w_algo
        + reg_contribution
        + agree_q["score"] * w_agree,
        3,
    )
    evidence_strength = max(0.0, min(1.0, evidence_strength))

    # ── Low evidence check ────────────────────────────────────────────────────
    low_evidence = evidence_strength < LOW_EVIDENCE_THRESHOLD

    if low_evidence:
        if secondary_evidence_available:
            sec_status = SecondaryEvidenceStatus.CONFIRMED
            sec_reason = secondary_evidence_note or "Secondary analysis was performed."
        else:
            sec_status = SecondaryEvidenceStatus.NO_SECONDARY_EVIDENCE_AVAILABLE
            sec_reason = (
                secondary_evidence_note
                or "No genuinely independent secondary evidence source is available for this input. "
                   "A secondary analysis was NOT manufactured to trigger a re-analysis demo."
            )
    else:
        sec_status = None
        sec_reason = None

    # ── Build breakdown dict ──────────────────────────────────────────────────
    breakdown = {
        "data_quality": data_q,
        "algorithm_confidence": algo_conf,
        "cross_method_agreement": agree_q,
    }
    if reg_q is not None:
        breakdown["registration_quality"] = reg_q

    formula = (
        f"evidence_strength = "
        f"{w_data:.2f} × data_quality({data_q['score']:.3f})"
        f" + {w_algo:.2f} × algo_confidence({algo_conf['score']:.3f})"
        f" + {WEIGHTS['registration_quality']:.2f} × registration({reg_q['score'] if reg_q else 'N/A'})"
        f" + {w_agree:.2f} × agreement({agree_q['score']:.3f})"
        f" = {evidence_strength:.3f}"
    )

    return EvidenceStrengthResult(
        evidence_strength=evidence_strength,
        confidence_level=_confidence_level(evidence_strength),
        breakdown=breakdown,
        formula=formula,
        low_evidence=low_evidence,
        secondary_evidence_status=sec_status,
        secondary_evidence_reason=sec_reason,
        interpretation=_interpret(evidence_strength),
    )
