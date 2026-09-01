"""
SatQuery AI — Scene Loader Abstraction

All specialist tools receive images through this interface.
The SceneLoader is the ONLY place that knows whether an image comes from:
  - a user upload
  - a synthetic demo asset
  - a real benchmark image on disk
  - a Bhoonidhi-acquired scene

This abstraction means real satellite imagery can replace synthetic demo
images without any code changes in specialist_tools.py or analysis_service.py.

Architecture:
  BaseSceneLoader (ABC)
    ├── SyntheticSceneLoader   — procedural demo imagery (tests, fallback demos)
    ├── DiskSceneLoader        — reads from data/raw/ or data/demo/
    └── UploadedSceneLoader    — from a user upload (in-memory bytes)

Tools receive a LoadedScene object with standardised fields regardless of source.
"""

import base64
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

from backend.schemas.provenance import InputProvenance
import json
from backend.tools import demo_imagery


# ── Scene container ───────────────────────────────────────────────────────────

@dataclass
class LoadedScene:
    """
    Standardised image container passed to all specialist tools.

    Tools MUST NOT assume any particular sensor or band structure without
    checking `band_semantics`. If `band_semantics` is empty, the tool
    must treat channels as RGB (or greyscale) only.
    """
    image_np: np.ndarray          # uint8 [H, W] or [H, W, C]
    image_b64: str                # base64 PNG for SSE/frontend delivery
    height: int
    width: int
    n_channels: int

    input_provenance: InputProvenance
    scene_id: Optional[str]       # matches a manifest key if DEMO_ASSET
    sensor: str                   # e.g. "Sentinel-2", "LISS-IV", "Unknown"
    acquisition_date: Optional[str]

    band_semantics: List[str] = field(default_factory=list)
    """
    Ordered list of band names, e.g. ["Green", "Red", "NIR"].
    EMPTY when bands are not verified from metadata.
    Tools must check this before claiming spectral indices.
    """

    metadata: dict = field(default_factory=dict)
    """
    Raw metadata from the source (EXIF, GeoTIFF tags, Bhoonidhi catalogue entry).
    Preserved as-is for audit.
    """

    source_path: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


# ── Abstract loader ───────────────────────────────────────────────────────────

class BaseSceneLoader(ABC):

    @abstractmethod
    def load(self, **kwargs) -> LoadedScene:
        """Load and return a LoadedScene."""
        ...

    @staticmethod
    def _np_to_b64(arr: np.ndarray) -> str:
        """Encode uint8 numpy array to base64 PNG."""
        if arr.ndim == 2:
            pil = Image.fromarray(arr, mode="L")
        elif arr.shape[2] == 1:
            pil = Image.fromarray(arr[:, :, 0], mode="L")
        else:
            pil = Image.fromarray(arr[:, :, :3], mode="RGB")
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()


# ── Synthetic scene loader ─────────────────────────────────────────────────────

class SyntheticSceneLoader(BaseSceneLoader):
    """
    Loads a procedurally generated image from demo_imagery.py.

    Purpose: automated tests and fallback demos ONLY.
    Results must be labelled SYNTHETIC_DATA.
    Must NOT be presented as primary remote-sensing capability evidence.

    Architecture note: to replace a synthetic demo with real imagery,
    swap this loader for DiskSceneLoader without changing any tool code.
    """

    def load(
        self,
        generator_fn,           # callable() → base64 str
        scene_id: Optional[str] = None,
        sensor: str = "Synthetic (Demo Only)",
        acquisition_date: Optional[str] = None,
        band_semantics: Optional[List[str]] = None,
    ) -> LoadedScene:
        b64 = generator_fn()
        raw = base64.b64decode(b64)
        pil = Image.open(io.BytesIO(raw)).convert("RGB")
        arr = np.array(pil, dtype=np.uint8)

        return LoadedScene(
            image_np=arr,
            image_b64=b64,
            height=arr.shape[0],
            width=arr.shape[1],
            n_channels=arr.shape[2],
            input_provenance=InputProvenance.SYNTHETIC_DATA,
            scene_id=scene_id,
            sensor=sensor,
            acquisition_date=acquisition_date,
            band_semantics=band_semantics or [],
            metadata={},
            warnings=[
                "SYNTHETIC_DATA: This image was procedurally generated. "
                "It is suitable for tests and fallback demos only. "
                "Replace with a DiskSceneLoader pointing to real imagery for production."
            ],
        )


# ── Disk scene loader ─────────────────────────────────────────────────────────

class DiskSceneLoader(BaseSceneLoader):
    """
    Loads an image from the local filesystem (data/raw/ or data/demo/).

    Supports:
      - PNG / JPEG: loaded as-is via Pillow → RGB uint8
      - Single-band TIFF: loaded as greyscale
      - Multi-band TIFF: loaded via tifffile; band_semantics populated
        ONLY when a metadata sidecar (*.json or *.txt) is present

    Band semantics:
      NEVER assumed from the file alone.
      Read from the metadata sidecar if available; otherwise left empty.
      Callers must check band_semantics before using spectral bands.
    """

    def load(
        self,
        filepath: str,
        scene_id: Optional[str] = None,
        input_provenance: InputProvenance = InputProvenance.REAL_SATELLITE_DATA,
        sensor: str = "Unknown",
        acquisition_date: Optional[str] = None,
    ) -> LoadedScene:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Scene file not found: {filepath}")

        suffix = path.suffix.lower()
        warnings = []
        band_semantics: List[str] = []
        raw_metadata: dict = {}

        if suffix in (".png", ".jpg", ".jpeg"):
            pil = Image.open(path).convert("RGB")
            arr = np.array(pil, dtype=np.uint8)
            band_semantics = []   # RGB assumed but NOT labelled as specific bands
            warnings.append(
                "PNG/JPEG loaded — band semantics unknown. "
                "Treating as visual RGB only."
            )

        elif suffix in (".tif", ".tiff"):
            arr, band_semantics, raw_metadata, tiff_warnings = _load_tiff(path)
            warnings.extend(tiff_warnings)

        else:
            raise ValueError(
                f"Unsupported file format '{suffix}'. "
                f"Supported: .png, .jpg, .jpeg, .tif, .tiff"
            )

        # Try loading metadata sidecar
        sidecar_bands, sidecar_meta, sidecar_warnings = _load_sidecar(path)
        warnings.extend(sidecar_warnings)
        if sidecar_bands:
            band_semantics = sidecar_bands
            raw_metadata.update(sidecar_meta)

        if arr.ndim == 2:
            h, w = arr.shape
            nc = 1
        else:
            h, w, nc = arr.shape

        b64 = self._np_to_b64(arr)

        return LoadedScene(
            image_np=arr,
            image_b64=b64,
            height=h,
            width=w,
            n_channels=nc,
            input_provenance=input_provenance,
            scene_id=scene_id,
            sensor=sensor,
            acquisition_date=acquisition_date,
            band_semantics=band_semantics,
            metadata=raw_metadata,
            source_path=str(filepath),
            warnings=warnings,
        )


# ── Uploaded scene loader ─────────────────────────────────────────────────────

class UploadedSceneLoader(BaseSceneLoader):
    """
    Loads an image from in-memory bytes (FastAPI UploadFile content).
    Provenance is always USER_UPLOAD.
    Band semantics: always empty (unknown).
    """

    def load(
        self,
        file_bytes: bytes,
        filename: str = "upload",
        sensor: str = "Unknown",
    ) -> LoadedScene:
        try:
            pil = Image.open(io.BytesIO(file_bytes))
        except Exception as exc:
            raise ValueError(f"Cannot decode uploaded file '{filename}': {exc}") from exc

        n_channels = len(pil.getbands())
        pil_rgb = pil.convert("RGB")
        arr = np.array(pil_rgb, dtype=np.uint8)
        h, w, nc = arr.shape
        b64 = self._np_to_b64(arr)

        warnings = []
        if n_channels == 4:
            warnings.append("Alpha channel present in upload — discarded, RGB retained.")
        if pil.mode == "P":
            warnings.append("Palette-mode image detected and converted to RGB.")

        return LoadedScene(
            image_np=arr,
            image_b64=b64,
            height=h,
            width=w,
            n_channels=nc,
            input_provenance=InputProvenance.USER_UPLOAD,
            scene_id=None,            # user uploads never match precomputed scenes
            sensor=sensor,
            acquisition_date=None,
            band_semantics=[],        # unknown — never assumed for user uploads
            metadata={"original_mode": pil.mode, "filename": filename},
            warnings=warnings,
        )


# ── TIFF loading helper ───────────────────────────────────────────────────────

def _load_tiff(path: Path) -> Tuple[np.ndarray, List[str], dict, List[str]]:
    """
    Load a GeoTIFF or multi-band TIFF.
    Band semantics are NOT assumed — returned as empty unless from sidecar.
    """
    warnings: List[str] = []
    band_semantics: List[str] = []
    meta: dict = {}

    try:
        import tifffile
        data = tifffile.imread(str(path))
        meta["tifffile_shape"] = list(data.shape)
        meta["tifffile_dtype"] = str(data.dtype)
    except ImportError:
        # Fallback to Pillow
        warnings.append("tifffile not available — using Pillow for TIFF loading (limited band support).")
        pil = Image.open(path)
        data = np.array(pil)
        meta["pillow_mode"] = pil.mode

    # Normalise to uint8
    if data.dtype != np.uint8:
        d_min, d_max = data.min(), data.max()
        if d_max > d_min:
            data = ((data - d_min) / (d_max - d_min) * 255).astype(np.uint8)
            warnings.append(
                f"TIFF dtype={meta.get('tifffile_dtype', 'unknown')} normalised to uint8. "
                f"Original range: [{d_min}, {d_max}]. "
                f"This normalisation affects quantitative analysis."
            )
        else:
            data = np.zeros_like(data, dtype=np.uint8)
            warnings.append("TIFF had zero dynamic range — filled with zeros.")

    # Handle axis order: tifffile returns (bands, H, W) for multi-band
    if data.ndim == 3 and data.shape[0] < data.shape[2]:
        data = np.moveaxis(data, 0, -1)  # → (H, W, bands)
        warnings.append(
            f"TIFF axes reordered from (bands, H, W) to (H, W, bands). "
            f"Band count: {data.shape[2]}. "
            f"Band semantics NOT assumed — verify from metadata sidecar."
        )

    return data, band_semantics, meta, warnings


# ── Metadata sidecar loader ───────────────────────────────────────────────────

def _load_sidecar(image_path: Path) -> Tuple[List[str], dict, List[str]]:
    """
    Attempt to load a JSON metadata sidecar file alongside the image.
    File: <image_stem>.json next to the image.

    Expected JSON structure:
    {
      "sensor": "LISS-IV MX",
      "acquisition_date": "2024-03-15",
      "band_semantics": ["Green", "Red", "NIR"],  <- from official NRSC metadata
      "band_notes": "Bands per NRSC LISS-IV MX product specification",
      ...
    }
    """
    sidecar_path = image_path.with_suffix(".json")
    if not sidecar_path.exists():
        return [], {}, []

    try:
        import json
        with open(sidecar_path) as f:
            meta = json.load(f)
        bands = meta.get("band_semantics", [])
        notes = meta.get("band_notes", "")
        warnings = []
        if bands:
            warnings.append(
                f"Band semantics loaded from sidecar {sidecar_path.name}: {bands}. "
                f"Note: {notes if notes else 'no additional notes.'}"
            )
        return bands, meta, warnings
    except Exception as exc:
        return [], {}, [f"Could not parse metadata sidecar {sidecar_path.name}: {exc}"]


# ── Scene Registry ────────────────────────────────────────────────────────────

def load_scene(scene_id: str) -> List["LoadedScene"]:
    """
    Load a scene by its ID from data/metadata/scenes.json.
    Automatically routes to DiskSceneLoader (real/benchmark data) or
    SyntheticSceneLoader (fallback procedural data).
    Returns a list of LoadedScene (usually 1, but 2 for bi-temporal).
    """
    registry_path = Path("data/metadata/scenes.json")
    if not registry_path.exists():
        raise FileNotFoundError(f"Scene registry not found at {registry_path}")

    with open(registry_path, "r") as f:
        registry = json.load(f)

    scenes = registry.get("scenes", {})
    if scene_id not in scenes:
        raise ValueError(f"Scene ID '{scene_id}' not found in registry.")

    meta = scenes[scene_id]
    prov_str = meta.get("input_provenance", "UNKNOWN")
    try:
        provenance = InputProvenance(prov_str)
    except ValueError:
        provenance = InputProvenance.UNKNOWN

    sensor = meta.get("sensors", ["Unknown"])[0]
    
    # Check if there is an image path provided (real data mode)
    image_paths = []
    if "image_t1_path" in meta and "image_t2_path" in meta:
        image_paths = [meta["image_t1_path"], meta["image_t2_path"]]
    elif "image_path" in meta:
        image_paths = [meta["image_path"]]

    # If it's real data and we have paths, use DiskSceneLoader
    if image_paths and all(Path(p).exists() for p in image_paths):
        loader = DiskSceneLoader()
        acq_date = meta.get("acquisition_date") or meta.get("acquisition_date_t1")
        return [
            loader.load(
                filepath=p,
                scene_id=scene_id,
                input_provenance=provenance,
                sensor=sensor,
                acquisition_date=acq_date
            ) for p in image_paths
        ]

    # Fallback to synthetic if marked as such or if real data missing
    loader = SyntheticSceneLoader()
    # Pick a generator based on scene ID/type
    if scene_id == "demo1" or "change" in scene_id.lower():
        return [
            loader.load(
                generator_fn=lambda: demo_imagery.generate_urban_scene("2024", expansion_factor=0.0),
                scene_id=scene_id, sensor=sensor, acquisition_date=None, band_semantics=[]
            ),
            loader.load(
                generator_fn=lambda: demo_imagery.generate_urban_scene("2026", expansion_factor=0.6),
                scene_id=scene_id, sensor=sensor, acquisition_date=None, band_semantics=[]
            )
        ]
    elif scene_id == "demo2" or "sar" in scene_id.lower():
        generator = lambda: demo_imagery.generate_sar_image()
    elif scene_id == "demo3" or "cloud" in scene_id.lower():
        generator = lambda: demo_imagery.generate_cloud_image()
    else:
        generator = lambda: demo_imagery.generate_urban_scene("Fallback", expansion_factor=0.0)

    return [loader.load(
        generator_fn=generator,
        scene_id=scene_id,
        sensor=sensor,
        acquisition_date=None,
        band_semantics=[]
    )]

