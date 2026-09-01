"""
SatQuery AI — Solution Space (Strategy Registry)
Maps task types to ordered tool execution workflows.
"""

from typing import Dict, List
from backend.schemas.models import TaskType


STRATEGY_REGISTRY: Dict[str, List[str]] = {

    TaskType.SINGLE_IMAGE: [
        "image_validation",
        "cloud_detection",
        "scene_understanding",
        "object_region_detection",
        "confidence_check",
        "answer_synthesis",
    ],

    TaskType.BI_TEMPORAL_CHANGE: [
        "image_validation",
        "cloud_detection",
        "bi_temporal_change_detection",
        "land_cover_classification",
        "spatial_reasoning",
        "evidence_comparison",
        "confidence_check",
        "answer_synthesis",
    ],

    TaskType.SAR_OPTICAL: [
        "image_validation",
        "scene_understanding",
        "sar_optical_fusion",
        "evidence_comparison",
        "confidence_check",
        "answer_synthesis",
    ],

    TaskType.CLOUD_ANALYSIS: [
        "image_validation",
        "cloud_detection",
        "cloud_reconstruction",
        "scene_understanding",
        "confidence_check",
        "answer_synthesis",
    ],

    TaskType.OBJECT_DETECTION: [
        "image_validation",
        "cloud_detection",
        "scene_understanding",
        "object_region_detection",
        "confidence_check",
        "answer_synthesis",
    ],

    TaskType.UNKNOWN: [
        "image_validation",
        "scene_understanding",
        "confidence_check",
        "answer_synthesis",
    ],
}


# Cloud reconstruction is OPTIONAL — inserted dynamically when cloud_detection
# returns a warning. Never in the base workflow unless the task IS cloud_analysis.
OPTIONAL_CLOUD_RECONSTRUCTION_TRIGGER = "cloud_detection"
CLOUD_RECONSTRUCTION_TOOL = "cloud_reconstruction"
CLOUD_THRESHOLD = 0.20  # 20% cloud coverage triggers reconstruction


def get_strategy(task_type: TaskType) -> List[str]:
    """Return the ordered tool list for a given task type."""
    return list(STRATEGY_REGISTRY.get(task_type, STRATEGY_REGISTRY[TaskType.UNKNOWN]))


def maybe_insert_cloud_reconstruction(
    plan: List[str], cloud_coverage: float
) -> tuple[List[str], bool]:
    """
    After cloud_detection runs, if coverage exceeds threshold,
    dynamically insert cloud_reconstruction into the plan.
    Returns (updated_plan, was_inserted).
    """
    inserted = False
    if (
        cloud_coverage >= CLOUD_THRESHOLD
        and CLOUD_RECONSTRUCTION_TOOL not in plan
        and OPTIONAL_CLOUD_RECONSTRUCTION_TRIGGER in plan
    ):
        idx = plan.index(OPTIONAL_CLOUD_RECONSTRUCTION_TRIGGER) + 1
        plan = plan[:idx] + [CLOUD_RECONSTRUCTION_TOOL] + plan[idx:]
        inserted = True
    return plan, inserted
