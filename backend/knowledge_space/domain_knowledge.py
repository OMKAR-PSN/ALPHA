"""
SatQuery AI — Domain Knowledge Space
Provides structured domain knowledge for the controller to use
when interpreting queries and generating explanations.
"""

from typing import Dict, Any

REMOTE_SENSING_KNOWLEDGE: Dict[str, Any] = {

    "sensors": {
        "Sentinel-2": {
            "type": "Optical / Multispectral",
            "bands": 13,
            "resolution_m": 10,
            "revisit_days": 5,
            "provider": "ESA Copernicus",
            "use_cases": ["land cover", "vegetation", "urban mapping", "water bodies"],
        },
        "Sentinel-1": {
            "type": "SAR (C-band)",
            "polarizations": ["VV", "VH"],
            "resolution_m": 10,
            "revisit_days": 6,
            "provider": "ESA Copernicus",
            "use_cases": ["flood detection", "urban areas", "cloud-penetration", "soil moisture"],
            "advantage": "Works through clouds and at night",
        },
        "LISS-IV": {
            "type": "Optical / Multispectral",
            "bands": 3,
            "resolution_m": 5.8,
            "provider": "ISRO / ResourceSat-2",
            "use_cases": ["urban planning", "crop monitoring", "high-res land use"],
        },
        "Landsat-8/9": {
            "type": "Optical / Multispectral",
            "bands": 11,
            "resolution_m": 30,
            "revisit_days": 16,
            "provider": "NASA / USGS",
            "use_cases": ["long-term change detection", "thermal analysis"],
        },
    },

    "task_definitions": {
        "bi_temporal_change": "Analysis comparing two images from different dates to detect changes.",
        "single_image": "Analysis of a single satellite scene for classification or understanding.",
        "sar_optical": "Cross-modal analysis combining SAR and optical imagery for robust interpretation.",
        "cloud_analysis": "Detection and removal of cloud contamination in optical imagery.",
        "object_detection": "Identification of specific objects or regions within a satellite scene.",
    },

    "land_cover_classes": [
        "Built-up / Urban",
        "Vegetation / Forest",
        "Agriculture",
        "Water body",
        "Bare soil / Fallow",
        "Road / Infrastructure",
        "Industrial",
        "Wetland",
    ],

    "change_types": [
        "Urban expansion",
        "Deforestation",
        "Flood inundation",
        "Agricultural conversion",
        "Drought / vegetation loss",
        "Coastal erosion",
        "New construction",
        "Infrastructure development",
    ],

    "cloud_concepts": {
        "cloud_contamination": (
            "Optical sensors cannot see through clouds. Cloud-contaminated pixels "
            "must be masked or reconstructed before analysis."
        ),
        "cloud_reconstruction": (
            "Cloud reconstruction uses SAR imagery (cloud-penetrating) or temporal "
            "compositing to estimate the ground truth beneath cloud cover."
        ),
        "cloud_shadow": (
            "Areas where clouds cast shadows are also compromised and require "
            "separate detection and treatment."
        ),
        "threshold_pct": 20,
    },

    "sar_concepts": {
        "backscatter": (
            "SAR measures electromagnetic backscatter. High backscatter from urban "
            "areas (double-bounce), low from smooth water surfaces."
        ),
        "fusion_benefit": (
            "SAR + Optical fusion improves accuracy by combining spectral richness "
            "of optical with all-weather capability of SAR."
        ),
        "limitations": "SAR speckle noise requires filtering; geometrical distortions possible.",
    },

    "query_intent_patterns": {
        "bi_temporal_keywords": [
            "changed", "change", "between", "2024", "2025", "2026",
            "before", "after", "increase", "decrease", "grow", "expand",
            "two dates", "temporal", "dates",
        ],
        "sar_keywords": [
            "sar", "radar", "sentinel-1", "microwave", "backscatter",
            "compare optical", "optical and sar",
        ],
        "cloud_keywords": [
            "cloud", "hazy", "haze", "obscured", "covered", "contaminated",
            "cloudy", "reconstructed",
        ],
        "object_keywords": [
            "identify", "find", "locate", "detect", "where is", "which areas",
            "show me", "mark", "highlight",
        ],
        "understanding_keywords": [
            "what is", "what's in", "describe", "present in", "show",
            "scene", "understand", "analyse", "analyze",
        ],
    },
}


def get_intent_keywords(category: str):
    return REMOTE_SENSING_KNOWLEDGE["query_intent_patterns"].get(category, [])


def get_sensor_info(sensor: str) -> Dict[str, Any]:
    return REMOTE_SENSING_KNOWLEDGE["sensors"].get(sensor, {})


def get_task_description(task_type: str) -> str:
    return REMOTE_SENSING_KNOWLEDGE["task_definitions"].get(task_type, "")
