"""
SatQuery AI — LISS-IV Ingestion Interface

LISS-IV (Linear Imaging Self-Scanner IV) is an ISRO/NRSC sensor on ResourceSat-2/2A.

IMPORTANT:
  This module does NOT hard-code LISS-IV's band structure.
  Band assignments are read from the official NRSC metadata supplied with
  the product, not assumed from generic specifications.

  Reason: LISS-IV has two modes:
    - MX (Multispectral): Green, Red, NIR  (3 bands at 5.8 m GSD)
    - PAN (Panchromatic): Single band      (5.8 m GSD)
  
  The specific band layout for a given product depends on:
    - Mode (MX or PAN)
    - Processing level
    - The actual metadata accompanying the downloaded product

  Any assumption beyond what the metadata states is a fabrication and will
  produce incorrect spectral analysis.

Ingestion pipeline:
  1. Locate and parse the NRSC product metadata file
     (XML or text, typically <ProductName>.xml or .hdr)
  2. Extract verified band list and band-to-channel mapping
  3. Load image file (GeoTIFF or raw band files)
  4. Build a LoadedScene with ONLY verified band_semantics
  5. Return with warnings for any missing or ambiguous metadata

Status:
  Real LISS-IV test data is NOT currently available.
  The ingestion interface is fully implemented.
  Call load_liss_iv() with a real product directory when data becomes available.

References:
  - NRSC Data Products Specification: https://bhuvan.nrsc.gov.in
  - Bhoonidhi portal: https://bhoonidhi.nrsc.gov.in
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree

from backend.tools.scene_loader import DiskSceneLoader, LoadedScene
from backend.schemas.provenance import InputProvenance


# ── Exceptions ────────────────────────────────────────────────────────────────

class LISSIVDataPending(Exception):
    """Raised when the method is called but no real LISS-IV data is available."""


class LISSIVMetadataError(ValueError):
    """Raised when required metadata cannot be parsed or verified."""


# ── NRSC metadata parser ──────────────────────────────────────────────────────

@dataclass
class LISSIVMetadata:
    """
    Structured metadata extracted from NRSC product metadata files.
    All fields that cannot be verified from metadata remain None.
    """
    product_id: Optional[str] = None
    sensor_mode: Optional[str] = None        # "MX" | "PAN" | None if not found
    acquisition_date: Optional[str] = None
    path_row: Optional[str] = None
    n_bands: Optional[int] = None
    band_semantics: List[str] = field(default_factory=list)
    """
    Band names in channel order, as stated in NRSC metadata.
    Example: ["Green", "Red", "NIR"] for LISS-IV MX product.
    EMPTY if not found in metadata.
    """
    band_notes: str = ""
    pixel_size_m: Optional[float] = None
    raw_metadata: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


def _parse_nrsc_xml(xml_path: Path) -> LISSIVMetadata:
    """
    Parse NRSC standard XML product metadata.
    Attempts to extract band information from official product descriptor.
    """
    meta = LISSIVMetadata()
    meta.raw_metadata["source"] = str(xml_path)

    try:
        tree = ElementTree.parse(str(xml_path))
        root = tree.getroot()
    except Exception as exc:
        meta.warnings.append(f"Could not parse XML metadata {xml_path.name}: {exc}")
        return meta

    # NRSC XML tags vary by product version; try multiple known tag names
    def find_text(*tags) -> Optional[str]:
        for tag in tags:
            el = root.find(f".//{tag}")
            if el is not None and el.text:
                return el.text.strip()
        return None

    meta.product_id    = find_text("ProductId", "product_id", "SceneId")
    meta.acquisition_date = find_text("SceneDate", "AcquisitionDate", "Date")
    meta.path_row      = find_text("PathRow", "path_row")

    # Sensor mode
    mode_text = find_text("SensorMode", "Mode", "sensor_mode")
    if mode_text:
        mode_upper = mode_text.upper()
        if "MX" in mode_upper or "MULTI" in mode_upper:
            meta.sensor_mode = "MX"
        elif "PAN" in mode_upper:
            meta.sensor_mode = "PAN"
        else:
            meta.sensor_mode = mode_text
            meta.warnings.append(
                f"Unrecognised sensor mode '{mode_text}' — band semantics left unassigned."
            )

    # Pixel size
    ps = find_text("PixelSpacing", "GSD", "PixelSize")
    if ps:
        try:
            meta.pixel_size_m = float(ps)
        except ValueError:
            meta.warnings.append(f"Could not parse pixel size value: {ps}")

    # Band information — look for BandList, BandNumber, or similar
    bands_el = root.findall(".//Band") or root.findall(".//BandInfo")
    if bands_el:
        band_names = []
        for b in bands_el:
            name = (
                b.get("name")
                or b.findtext("BandName")
                or b.findtext("Name")
                or b.findtext("WaveBand")
            )
            if name:
                band_names.append(name.strip())
        if band_names:
            meta.band_semantics = band_names
            meta.n_bands = len(band_names)
            meta.band_notes = f"Band semantics from NRSC XML metadata ({xml_path.name})."
        else:
            meta.warnings.append(
                "Band elements found in XML but no band names extracted. "
                "band_semantics left empty."
            )
    else:
        meta.warnings.append(
            "No band information found in XML metadata. "
            "band_semantics left empty — do NOT assume band layout."
        )

    meta.raw_metadata["parsed_xml_tags"] = {
        "product_id": meta.product_id,
        "sensor_mode": meta.sensor_mode,
        "acquisition_date": meta.acquisition_date,
        "n_bands": meta.n_bands,
        "pixel_size_m": meta.pixel_size_m,
    }
    return meta


def _parse_sidecar_json(json_path: Path) -> LISSIVMetadata:
    """
    Parse a manually curated JSON metadata sidecar.
    Used when NRSC XML is unavailable or needs augmentation.

    Expected format (band_semantics is what matters):
    {
      "product_id": "...",
      "sensor": "LISS-IV MX",
      "sensor_mode": "MX",
      "acquisition_date": "2024-03-15",
      "band_semantics": ["Green", "Red", "NIR"],
      "band_notes": "Per NRSC RS2 LISS-IV MX product specification, downloaded from Bhoonidhi",
      "pixel_size_m": 5.8
    }
    """
    meta = LISSIVMetadata()
    meta.raw_metadata["source"] = str(json_path)

    try:
        with open(json_path) as f:
            data = json.load(f)
    except Exception as exc:
        meta.warnings.append(f"Could not parse sidecar JSON {json_path.name}: {exc}")
        return meta

    meta.product_id      = data.get("product_id")
    meta.sensor_mode     = data.get("sensor_mode")
    meta.acquisition_date = data.get("acquisition_date")
    meta.band_semantics  = data.get("band_semantics", [])
    meta.band_notes      = data.get("band_notes", "From manually curated JSON sidecar.")
    meta.n_bands         = len(meta.band_semantics) if meta.band_semantics else data.get("n_bands")
    meta.raw_metadata    = data

    if not meta.band_semantics:
        meta.warnings.append(
            "JSON sidecar has no band_semantics field. "
            "band_semantics left empty — do NOT assume band layout."
        )

    return meta


# ── Main ingestion function ───────────────────────────────────────────────────

def load_liss_iv(product_dir: str) -> LoadedScene:
    """
    Load a LISS-IV product from a directory.

    Args:
        product_dir: Path to the NRSC product folder.
                     Expected contents:
                       - One or more .tif/.tiff image files (bands)
                       - Optional: <ProductName>.xml (NRSC standard metadata)
                       - Optional: metadata.json (curated sidecar)

    Returns:
        LoadedScene with band_semantics populated ONLY from verified metadata.

    Raises:
        LISSIVDataPending: If no real LISS-IV data is found (correct behaviour
            when data is not yet available).
        LISSIVMetadataError: If image files exist but metadata cannot be parsed.
    """
    pdir = Path(product_dir)

    if not pdir.exists():
        raise LISSIVDataPending(
            f"LISS-IV product directory not found: {product_dir}. "
            f"Real LISS-IV data is not yet available. "
            f"Obtain data from Bhoonidhi portal (https://bhoonidhi.nrsc.gov.in) "
            f"and place it in this directory."
        )

    # ── Find image file ───────────────────────────────────────────────────────
    image_files = sorted(pdir.glob("*.tif")) + sorted(pdir.glob("*.tiff"))
    if not image_files:
        raise LISSIVDataPending(
            f"No TIFF image files found in {product_dir}. "
            f"Real LISS-IV data is not yet available."
        )

    # ── Find metadata ─────────────────────────────────────────────────────────
    liss_meta = LISSIVMetadata()
    liss_meta.warnings.append(
        "No NRSC metadata found — band semantics unverified. "
        "band_semantics left empty."
    )

    # Priority: XML first, JSON sidecar second
    xml_files  = list(pdir.glob("*.xml"))
    json_files = [pdir / "metadata.json"] + list(pdir.glob("*.json"))

    if xml_files:
        liss_meta = _parse_nrsc_xml(xml_files[0])
        if not liss_meta.band_semantics and any(f.exists() for f in json_files):
            # Augment with JSON if XML didn't give bands
            json_meta = _parse_sidecar_json(next(f for f in json_files if f.exists()))
            if json_meta.band_semantics:
                liss_meta.band_semantics = json_meta.band_semantics
                liss_meta.band_notes = json_meta.band_notes
                liss_meta.warnings.append(
                    "Band semantics augmented from JSON sidecar "
                    f"(XML had {len(xml_files)} file(s) but no band names)."
                )
    elif any(f.exists() for f in json_files):
        liss_meta = _parse_sidecar_json(next(f for f in json_files if f.exists()))

    # ── Load image via DiskSceneLoader ────────────────────────────────────────
    loader = DiskSceneLoader()
    scene = loader.load(
        filepath=str(image_files[0]),
        scene_id=pdir.name,
        input_provenance=InputProvenance.REAL_SATELLITE_DATA,
        sensor=f"LISS-IV {liss_meta.sensor_mode or '(mode unknown)'}",
        acquisition_date=liss_meta.acquisition_date,
    )

    # Attach LISS-IV metadata
    scene.band_semantics = liss_meta.band_semantics  # only from metadata
    scene.metadata["liss_iv"] = {
        "product_id":      liss_meta.product_id,
        "sensor_mode":     liss_meta.sensor_mode,
        "n_bands_declared": liss_meta.n_bands,
        "band_semantics":  liss_meta.band_semantics,
        "band_notes":      liss_meta.band_notes,
        "pixel_size_m":    liss_meta.pixel_size_m,
    }
    scene.warnings.extend(liss_meta.warnings)

    # Final band count check
    actual_bands = scene.n_channels
    if liss_meta.n_bands and actual_bands != liss_meta.n_bands:
        scene.warnings.append(
            f"Band count mismatch: metadata declares {liss_meta.n_bands} bands, "
            f"image file has {actual_bands} channels. "
            f"band_semantics may not align with actual channels."
        )

    return scene
