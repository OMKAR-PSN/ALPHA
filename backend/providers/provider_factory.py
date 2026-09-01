"""
SatQuery AI — Provider Factory

Selects the best available provider for reconstruction tasks using a
priority chain:

  1. PrecomputedProvider  — if scene_id matches a known manifest (demo scenes)
  2. RemoteGPUProvider    — if SATQUERY_GPU_ENDPOINT is configured
  3. CPUInpaintingProvider — always available as CPU baseline

Usage:
    from backend.providers.provider_factory import get_reconstruction_provider
    provider = get_reconstruction_provider(scene_id="emrdm_demo_cloud_001")
    result = provider.reconstruct(image_b64, mask_b64, scene_id, provenance)
"""

from typing import Optional

from backend.providers.base import BaseProvider
from backend.providers.cpu_provider import CPUInpaintingProvider
from backend.providers.precomputed_provider import PrecomputedProvider
from backend.providers.remote_gpu_provider import RemoteGPUProvider

_cpu_provider = CPUInpaintingProvider()
_remote_provider = RemoteGPUProvider()
_precomputed_provider = PrecomputedProvider()


def get_reconstruction_provider(scene_id: Optional[str] = None) -> BaseProvider:
    """
    Select the appropriate reconstruction provider.

    Priority:
      1. If scene_id is given and a precomputed manifest exists for it
         → PrecomputedProvider (verified GPU output)
      2. If a remote GPU endpoint is configured
         → RemoteGPUProvider (live GPU inference)
      3. Fallback
         → CPUInpaintingProvider (always available)

    Note: user-uploaded images (scene_id=None) skip step 1 entirely,
    guaranteeing they never receive a precomputed result.
    """
    # Step 1 — precomputed demo asset
    if scene_id is not None and _precomputed_provider.is_available():
        known = _precomputed_provider.list_available_scenes()
        if scene_id in known:
            return _precomputed_provider

    # Step 2 — remote GPU
    if _remote_provider.is_available():
        return _remote_provider

    # Step 3 — CPU fallback (always)
    return _cpu_provider


def get_provider_status() -> dict:
    """Return the availability status of all providers (for /api/health)."""
    return {
        "cpu_inpainting": _cpu_provider.is_available(),
        "remote_gpu": _remote_provider.is_available(),
        "precomputed_demo": _precomputed_provider.is_available(),
        "available_demo_scenes": (
            _precomputed_provider.list_available_scenes()
            if _precomputed_provider.is_available()
            else []
        ),
    }
