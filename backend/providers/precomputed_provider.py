"""
SatQuery AI — Precomputed Model Output Provider

Loads verified model outputs that were generated externally on a GPU machine
and stored as demo assets.

STRICT SAFETY RULES:
  1. A precomputed result is ONLY returned when scene_id matches a manifest entry exactly.
  2. User-uploaded images (scene_id=None) NEVER receive a precomputed result.
  3. If scene_id is unknown, the provider raises PrecomputedSceneNotFound —
     the caller must fall back to CPUInpaintingProvider.
  4. The manifest.json must contain a sha256 hash of the input and output files.
     If the hash cannot be verified, the provider returns a warning.

Manifest format (data/demo/<scene_id>/manifest.json):
{
  "scene_id": "emrdm_demo_cloud_001",
  "model": "EMRDM",
  "model_version": null,            <- null until verified from real GPU run
  "repository_url": "https://github.com/Ly403/EMRDM",
  "repository_commit": null,        <- populate after actual run
  "checkpoint": null,               <- populate after actual run
  "checkpoint_sha256": null,
  "input_filename": "cloudy_input.png",
  "input_sha256": null,             <- populate after actual run
  "output_filename": "reconstruction_output.png",
  "output_sha256": null,            <- populate after actual run
  "device": null,                   <- e.g. "NVIDIA A100 40GB"
  "execution_timestamp": null,      <- ISO 8601
  "runtime_seconds": null,
  "precomputed": true,
  "notes": "Placeholder manifest — GPU run not yet performed."
}

Fields that are null are NOT fabricated. They remain null until the team
runs the actual GPU inference and fills them in.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from backend.providers.base import BaseProvider, ProviderResult
from backend.schemas.provenance import ExecutionMode, InputProvenance


class PrecomputedSceneNotFound(ValueError):
    """Raised when the requested scene_id has no precomputed manifest."""


class PrecomputedProvider(BaseProvider):
    """
    Serves GPU-generated outputs that were stored as verified assets.

    The demo asset directory is configurable via SATQUERY_DEMO_DATA_DIR
    environment variable (default: data/demo/).
    """

    DEFAULT_DEMO_DIR = Path("data") / "demo"

    @property
    def name(self) -> str:
        return "PrecomputedProvider"

    def _demo_dir(self) -> Path:
        env_dir = os.environ.get("SATQUERY_DEMO_DATA_DIR", "")
        return Path(env_dir) if env_dir else self.DEFAULT_DEMO_DIR

    def is_available(self) -> bool:
        """Available iff at least one scene manifest exists."""
        demo_dir = self._demo_dir()
        if not demo_dir.exists():
            return False
        return any((demo_dir / name / "manifest.json").exists() for name in os.listdir(demo_dir))

    def list_available_scenes(self) -> list:
        """Return list of scene_ids with valid manifests."""
        demo_dir = self._demo_dir()
        scenes = []
        if demo_dir.exists():
            for name in os.listdir(demo_dir):
                manifest_path = demo_dir / name / "manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path) as f:
                            m = json.load(f)
                        if m.get("precomputed") is True:
                            scenes.append(m.get("scene_id", name))
                    except Exception:
                        pass
        return scenes

    def reconstruct(
        self,
        image_b64: str,
        mask_b64: str,
        scene_id: Optional[str] = None,
        input_provenance: InputProvenance = InputProvenance.UNKNOWN,
    ) -> ProviderResult:
        """
        Return a precomputed reconstruction ONLY if scene_id is known.

        Never call this with scene_id=None for user uploads.
        """
        # Safety guard: never serve precomputed to user-uploaded images
        if scene_id is None:
            raise PrecomputedSceneNotFound(
                "PrecomputedProvider cannot serve user-uploaded images. "
                "Use CPUInpaintingProvider or RemoteGPUProvider instead."
            )

        demo_dir = self._demo_dir()
        scene_dir = demo_dir / scene_id

        manifest_path = scene_dir / "manifest.json"
        if not manifest_path.exists():
            raise PrecomputedSceneNotFound(
                f"No precomputed manifest found for scene_id='{scene_id}'. "
                f"Expected: {manifest_path}"
            )

        with open(manifest_path) as f:
            manifest = json.load(f)

        if not manifest.get("precomputed"):
            raise PrecomputedSceneNotFound(
                f"Manifest for scene_id='{scene_id}' does not declare precomputed=true."
            )

        output_filename = manifest.get("output_filename", "reconstruction_output.png")
        output_path = scene_dir / output_filename

        if not output_path.exists():
            raise FileNotFoundError(
                f"Precomputed output file missing: {output_path}. "
                f"GPU run not yet performed for scene '{scene_id}'."
            )

        # Load and encode
        with open(output_path, "rb") as f:
            raw = f.read()
        output_b64 = base64.b64encode(raw).decode()

        # Verify SHA256 if available
        warnings = []
        declared_sha = manifest.get("output_sha256")
        if declared_sha:
            actual_sha = hashlib.sha256(raw).hexdigest()
            if actual_sha != declared_sha:
                warnings.append(
                    f"SHA256 mismatch for output file. "
                    f"Declared: {declared_sha[:16]}… Actual: {actual_sha[:16]}…"
                )
        else:
            warnings.append(
                "output_sha256 not populated in manifest — output integrity unverified. "
                "Populate after running actual GPU inference."
            )

        if manifest.get("repository_commit") is None:
            warnings.append(
                "repository_commit is null in manifest — model version untracked. "
                "Populate after actual GPU run."
            )

        return ProviderResult(
            output_b64=output_b64,
            execution_mode=ExecutionMode.PRECOMPUTED_MODEL_OUTPUT,
            algorithm=manifest.get("model", "UNKNOWN_MODEL"),
            input_provenance=InputProvenance.DEMO_ASSET,
            success=True,
            message=(
                f"Precomputed reconstruction loaded for scene '{scene_id}'. "
                f"Model: {manifest.get('model', 'unknown')}. "
                f"GPU device: {manifest.get('device') or 'not recorded'}."
            ),
            runtime_ms=int(manifest["runtime_seconds"] * 1000) if manifest.get("runtime_seconds") else None,
            model_id=manifest.get("model"),
            checkpoint=manifest.get("checkpoint"),
            warnings=warnings,
        )
