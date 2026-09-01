"""
SatQuery AI — Central Controller
Interprets natural-language queries and produces structured analysis plans.

Design Principle:
- The controller UNDERSTANDS, PLANS, SELECTS, and ORCHESTRATES
- It does NOT perform image analysis itself
- Specialist tools perform the actual analysis
"""

import re
from typing import Any, Dict, List, Tuple
from backend.schemas.models import TaskType, ControllerPlan
from backend.knowledge_space.domain_knowledge import get_intent_keywords
from backend.solution_space.strategy_registry import get_strategy


class CentralController:
    """
    Deterministic task router + intent extractor.
    
    Primary layer: keyword/pattern-based routing (reliable, no API key needed)
    Future layer: LLM call for richer semantic interpretation (swap-in ready)
    """

    CONFIDENCE_THRESHOLD = 0.75
    MAX_REANALYSIS = 2

    def interpret_query(self, query: str, image_count: int = 1) -> ControllerPlan:
        """
        Parse a natural-language query and return a structured plan.
        """
        q = query.lower().strip()

        task_type, intent, reasoning = self._classify_task(q, image_count)
        target, spatial_ref = self._extract_entities(q)
        dates = self._extract_dates(q)
        requires_sar = self._detect_sar_need(q)
        tools = get_strategy(task_type)

        return ControllerPlan(
            task_type=task_type,
            intent=intent,
            target=target,
            spatial_reference=spatial_ref,
            temporal=task_type == TaskType.BI_TEMPORAL_CHANGE,
            dates=dates,
            requires_sar=requires_sar,
            tools=tools,
            reasoning=reasoning,
        )

    def _classify_task(
        self, query: str, image_count: int
    ) -> Tuple[TaskType, str, str]:
        """Classify task type using keyword matching."""

        bi_keywords = get_intent_keywords("bi_temporal_keywords")
        sar_keywords = get_intent_keywords("sar_keywords")
        cloud_keywords = get_intent_keywords("cloud_keywords")
        object_keywords = get_intent_keywords("object_keywords")

        bi_score = sum(1 for kw in bi_keywords if kw in query)
        sar_score = sum(1 for kw in sar_keywords if kw in query)
        cloud_score = sum(1 for kw in cloud_keywords if kw in query)
        obj_score = sum(1 for kw in object_keywords if kw in query)

        # SAR+Optical
        if sar_score >= 1 or (image_count >= 2 and "sar" in query):
            return (
                TaskType.SAR_OPTICAL,
                "Cross-modal SAR and optical analysis",
                "SAR keywords detected. SAR-Optical fusion workflow selected.",
            )

        # Cloud
        if cloud_score >= 2:
            return (
                TaskType.CLOUD_ANALYSIS,
                "Cloud contamination analysis and reconstruction",
                "Cloud keywords detected. Cloud-first workflow selected.",
            )

        # Bi-temporal
        if bi_score >= 2 or image_count == 2:
            return (
                TaskType.BI_TEMPORAL_CHANGE,
                "Bi-temporal change detection analysis",
                "Temporal keywords detected with multiple images. Change analysis workflow selected.",
            )

        # Object detection
        if obj_score >= 2:
            return (
                TaskType.OBJECT_DETECTION,
                "Object and region identification",
                "Object detection keywords detected.",
            )

        # Default single image
        return (
            TaskType.SINGLE_IMAGE,
            "Single-image scene understanding",
            "No strong multi-temporal or SAR signals. Single-image analysis selected.",
        )

    def _extract_entities(self, query: str) -> Tuple[str, str | None]:
        """Extract target object and spatial reference."""
        targets = {
            "built-up": ["built.up", "urban", "building", "construction", "city", "town"],
            "water body": ["water", "lake", "pond", "reservoir", "flood"],
            "vegetation": ["vegetation", "forest", "trees", "green"],
            "river": ["river", "stream", "canal"],
            "agricultural land": ["farm", "crop", "agriculture", "agricultural"],
        }
        spatial_refs = {
            "river": ["river", "stream", "canal", "waterway"],
            "road": ["road", "highway", "street"],
            "coastline": ["coast", "shore", "beach", "sea"],
        }

        target = "general land cover"
        for label, keywords in targets.items():
            if any(re.search(kw, query) for kw in keywords):
                target = label
                break

        spatial_ref = None
        for label, keywords in spatial_refs.items():
            if any(re.search(kw, query) for kw in keywords):
                spatial_ref = label
                break

        return target, spatial_ref

    def _extract_dates(self, query: str) -> List[str]:
        """Extract years or date references from query."""
        return re.findall(r"\b(20\d{2})\b", query)

    def _detect_sar_need(self, query: str) -> bool:
        return any(kw in query for kw in get_intent_keywords("sar_keywords"))

    def generate_step_descriptions(self, tools: List[str]) -> List[Dict[str, str]]:
        """Map tool names to human-readable step descriptions for the UI trace."""
        descriptions = {
            "image_validation": {
                "name": "Input Validation",
                "description": "Checking image format, alignment, and metadata",
            },
            "cloud_detection": {
                "name": "Cloud Detection",
                "description": "Scanning for cloud contamination in optical imagery",
            },
            "cloud_reconstruction": {
                "name": "Cloud Reconstruction",
                "description": "⚡ AUTO-INSERTED: Reconstructing cloud-obscured pixels via SAR + temporal compositing",
                "is_auto_inserted": True,
            },
            "scene_understanding": {
                "name": "Scene Understanding",
                "description": "Classifying dominant land-cover components",
            },
            "object_region_detection": {
                "name": "Object & Region Detection",
                "description": "Localising specific features and regions of interest",
            },
            "land_cover_classification": {
                "name": "Land Cover Classification",
                "description": "Pixel-level classification into standard land-cover categories",
            },
            "bi_temporal_change_detection": {
                "name": "Change Detection",
                "description": "Detecting pixel-level changes between dates",
            },
            "sar_optical_fusion": {
                "name": "SAR–Optical Fusion",
                "description": "Fusing SAR and optical imagery for robust classification",
            },
            "spatial_reasoning": {
                "name": "Spatial Relationship Analysis",
                "description": "Analysing spatial relationships (distance, adjacency, buffering)",
            },
            "evidence_comparison": {
                "name": "Evidence Cross-Check",
                "description": "Comparing outputs across tools for consistency",
            },
            "confidence_check": {
                "name": "Confidence Assessment",
                "description": "Aggregating confidence scores and checking thresholds",
            },
            "answer_synthesis": {
                "name": "Answer Synthesis",
                "description": "Generating the final evidence-grounded natural-language answer",
            },
        }
        steps = []
        for i, tool in enumerate(tools):
            desc = descriptions.get(tool, {"name": tool.replace("_", " ").title(), "description": ""})
            steps.append({
                "step_index": i,
                "tool_name": tool,
                "step_name": desc["name"],
                "description": desc["description"],
                "is_auto_inserted": desc.get("is_auto_inserted", False),
            })
        return steps
