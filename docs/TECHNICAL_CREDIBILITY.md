# SatQuery AI — Technical Credibility Document

> **Version:** 1.1.0-credibility  
> **Environment:** CPU-only (Python 3.13, Windows)  
> **GPU model runs:** Not yet performed — EMRDM offline script prepared but not executed

---

## What Is Real

### Real CPU algorithms running on actual pixels

| Algorithm | Module | Test |
|---|---|---|
| `rgb_cloud_detector_v1` | `backend/tools/cloud_detector.py` | `tests/test_cloud_detector.py` — 15/15 pass |
| `abs_diff_otsu_v1` | `backend/tools/change_detector.py` | `tests/test_change_detector.py` — 13/13 pass |
| `ECC_registration` | `backend/tools/registration.py` | Exercised in change detector tests |
| `opencv_telea_inpaint` | `backend/providers/cpu_provider.py` | Called via ProviderFactory |
| `evidence_strength_calculator_v1` | `backend/tools/evidence.py` | `tests/test_provenance.py` — 22/22 pass |
| `pillow_image_validator_v1` | `backend/tools/specialist_tools.py` | Runs on real uploads |

**Total test coverage: 50 tests, 50 pass**

### Real upload pipeline

- `POST /api/upload` → validates image, loads via `UploadedSceneLoader`, returns base64
- Uploaded images passed to all tools via `uploaded_images` field in `/api/analyze`
- When real images present: cloud detection + change detection run on actual pixels

### Real evidence scoring

The `EvidenceStrengthScore` (0–1) is computed from four documented factors:

```
evidence_strength =
    0.25 × data_quality_score
  + 0.30 × algorithm_confidence
  + 0.25 × registration_quality_score
  + 0.20 × cross_method_agreement
```

Each factor has a documented rationale — see `backend/tools/evidence.py`.

---

## What Is Not Yet Real (Honestly Labelled)

| Feature | Status | Label in UI |
|---|---|---|
| EMRDM cloud reconstruction | GPU model pending | `SIMULATED` / `DEMO` badge |
| SAR-optical fusion | No real SAR input | `SAR_NOT_AVAILABLE` |
| Scene understanding | No land-cover model | `SIMULATED` + excluded from evidence |
| Object detection | No detection model | `SIMULATED` + excluded from evidence |
| Land cover classification | No spectral bands | `SIMULATED` + excluded from evidence |
| Spatial reasoning | No georeference | `SIMULATED` + excluded from evidence |
| LISS-IV data | Bhoonidhi credentials needed | `LISSIVDataPending` exception |
| Bhoonidhi catalogue | Credentials not set | `BhoonidhiUnavailableResult` |

### Evidence Exclusion Rule

Any tool with `execution_mode == SIMULATED` or `evidence_excludable == True` is **excluded** from evidence scoring. A `[DEMO]` badge appears in the UI trace. This prevents simulated values from inflating the evidence strength score.

---

## LISS-IV Band Structure

**LISS-IV band assignments are never hard-coded.**  
Bands are read from NRSC product metadata XML or a JSON sidecar, verified at load time.  
Without metadata: `band_semantics` = `[]`, and tools that require spectral bands raise a warning.

LISS-IV modes:
- **MX (Multispectral):** Green, Red, NIR (3 bands at 5.8 m GSD) — from NRSC official spec
- **PAN (Panchromatic):** Single band (5.8 m GSD)

Band assignments come from `backend/tools/liss_iv_ingestion.py` → `_parse_nrsc_xml()`.

---

## Registration Gating

Change detection is **blocked** when registration fails:

```python
if registration_result.quality == RegistrationQuality.FAILED:
    return ChangeDetectionResult(
        unreliable_registration=True,
        changed_area_pct=None,   # never reported
        change_mask_b64=None,    # never sent to frontend
        ...
    )
```

The SSE event for this result carries `registration_quality: "FAILED"` and `evidence_excludable: True`.  
The frontend shows a red `UNRELIABLE_REG` badge on the trace row.

---

## Secondary Evidence Policy

When `evidence_strength < 0.55`:

1. Check whether a genuinely independent secondary evidence source exists.
2. If **none exists**: return `NO_SECONDARY_EVIDENCE_AVAILABLE`.  
   Do **NOT** manufacture a secondary analysis to trigger the demo.
3. If a real secondary source was checked: return `CONFIRMED`.

A `LOW_EVIDENCE` SSE event is emitted with the status in the agent trace.  
The `secondary_evidence_reason` field is always human-readable.

---

## Synthetic Scenes

Demo scenes use procedurally generated imagery (`backend/tools/demo_imagery.py`).

- All synthetic scenes carry `InputProvenance.SYNTHETIC_DATA`.
- The `SyntheticSceneLoader` warns: `"SYNTHETIC_DATA: suitable for tests and fallback demos only."`
- Demo manifests in `data/demo/*/manifest.json` have `"precomputed": false` until a real GPU run is recorded.
- To replace a synthetic demo with real imagery: swap `SyntheticSceneLoader` → `DiskSceneLoader` at the tool call site without changing tool code.

---

## EMRDM GPU Inference (Future)

GPU run preparation:

1. Clone EMRDM: `git clone https://github.com/Ly403/EMRDM`
2. Run: `python scripts/run_emrdm_offline.py --input ... --mask ... --output data/demo/emrdm_demo_cloud_001/ --scene emrdm_demo_cloud_001`
3. Script saves output + updates `manifest.json` with SHA256 hashes and device info.
4. Set `SATQUERY_DEMO_DATA_DIR` → `PrecomputedProvider` serves the verified asset.

Until this is done: `cpu_provider.py` (OpenCV TELEA inpainting) is the live fallback.

---

## Bhoonidhi Connector

- Set `BHOONIDHI_USER` and `BHOONIDHI_PASSWORD` environment variables.
- `GET /api/health` shows `"bhoonidhi": {"configured": true/false}`.
- Without credentials: graceful fallback, no exceptions, no data download.
- Download size limit: 500 MB (configurable in `bhoonidhi_client.py`).

---

## Running Tests

```powershell
cd C:\Users\Omkar\Desktop\SIH_26
python -m pytest tests/ -v
# Expected: 50 passed
```

## Starting Backend

```powershell
python -m uvicorn backend.main:app --reload --port 8000
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

## Starting Frontend

```powershell
cd satquery-ai
npm run dev
# http://localhost:5173
```
