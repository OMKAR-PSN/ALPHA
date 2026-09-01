"""
SatQuery AI — Bhoonidhi STAC API Connector (Optional)

Bhoonidhi is the NRSC/ISRO satellite data portal.
This connector is OPTIONAL — the application functions without it.

Credentials are read ONLY from environment variables.
Never hard-coded. Never downloaded automatically.

Environment variables:
  BHOONIDHI_USER      — your registered Bhoonidhi username
  BHOONIDHI_PASSWORD  — your Bhoonidhi account password

Without credentials:
  is_configured() → False
  All methods return BhoonidhiUnavailableResult instead of raising exceptions.
  The application continues with local demo/benchmark scenes.

API notes (as of 2024):
  Base URL: https://bhoonidhi.nrsc.gov.in/bhoonidhi/api/
  Auth:      POST /login → JWT token (Bearer)
  Search:    POST /stac/search (STAC-compliant)
  Download:  Via product-specific link in search response

IMPORTANT:
  - Do NOT download large scenes automatically.
  - download_scene() requires explicit caller approval.
  - Token is cached for the session to avoid repeated logins.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── API constants ─────────────────────────────────────────────────────────────

BHOONIDHI_BASE_URL = "https://bhoonidhi.nrsc.gov.in/bhoonidhi/api"
LOGIN_ENDPOINT     = f"{BHOONIDHI_BASE_URL}/login"
SEARCH_ENDPOINT    = f"{BHOONIDHI_BASE_URL}/stac/search"
TOKEN_TTL_SECONDS  = 3600   # re-authenticate after 1 hour


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class BhoonidhiUnavailableResult:
    """Returned when credentials are not configured or API is unreachable."""
    available: bool = False
    reason: str = "Bhoonidhi credentials not configured."
    fallback: str = "Using local demo/benchmark scene instead."


@dataclass
class BhoonidhiScene:
    """Metadata for a single scene from Bhoonidhi STAC search."""
    product_id: str
    sensor: str
    acquisition_date: str
    bbox: List[float]               # [west, south, east, north]
    cloud_cover_pct: Optional[float]
    download_url: Optional[str]
    raw_stac: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BhoonidhiSearchResult:
    available: bool
    scenes: List[BhoonidhiScene] = field(default_factory=list)
    total_found: int = 0
    query_bbox: Optional[List[float]] = None
    query_date_range: Optional[str] = None
    query_sensor: Optional[str] = None
    message: str = ""
    warnings: List[str] = field(default_factory=list)


# ── Client ────────────────────────────────────────────────────────────────────

class BhoonidhiClient:
    """
    Optional STAC search and download client for Bhoonidhi.

    Usage:
        client = BhoonidhiClient()
        if not client.is_configured():
            return BhoonidhiUnavailableResult()

        results = client.search_catalogue(
            bbox=[72.8, 18.9, 73.1, 19.2],
            date_range=("2024-01-01", "2024-03-31"),
            sensor="LISS-IV",
            max_results=5,
        )
    """

    def __init__(self):
        self._user     = os.environ.get("BHOONIDHI_USER", "").strip()
        self._password = os.environ.get("BHOONIDHI_PASSWORD", "").strip()
        self._token: Optional[str] = None
        self._token_fetched_at: float = 0.0

    # ── Availability ──────────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        """Return True iff both credentials are set in the environment."""
        return bool(self._user and self._password)

    def unavailable_result(self, extra_reason: str = "") -> BhoonidhiUnavailableResult:
        reason = (
            "BHOONIDHI_USER and/or BHOONIDHI_PASSWORD environment variables are not set."
            if not self.is_configured()
            else extra_reason or "Bhoonidhi API is not available."
        )
        return BhoonidhiUnavailableResult(available=False, reason=reason)

    # ── Authentication ─────────────────────────────────────────────────────────

    def _authenticate(self) -> bool:
        """
        Obtain a JWT token from Bhoonidhi.
        Caches token for TOKEN_TTL_SECONDS.
        Returns True on success.
        """
        if self._token and (time.time() - self._token_fetched_at) < TOKEN_TTL_SECONDS:
            return True   # token still valid

        try:
            import requests
            resp = requests.post(
                LOGIN_ENDPOINT,
                json={"username": self._user, "password": self._password},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            token = data.get("token") or data.get("access_token") or data.get("jwt")
            if not token:
                logger.warning("Bhoonidhi login response did not contain a token field.")
                return False
            self._token = token
            self._token_fetched_at = time.time()
            logger.info("Bhoonidhi authentication successful.")
            return True
        except Exception as exc:
            logger.warning("Bhoonidhi authentication failed: %s", exc)
            self._token = None
            return False

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    # ── STAC Search ───────────────────────────────────────────────────────────

    def search_catalogue(
        self,
        bbox: List[float],
        date_range: tuple,          # ("YYYY-MM-DD", "YYYY-MM-DD")
        sensor: Optional[str] = None,
        max_results: int = 10,
    ):
        """
        Search Bhoonidhi STAC catalogue.

        Args:
            bbox:        [west, south, east, north] in WGS84.
            date_range:  (start_date, end_date) as ISO 8601 strings.
            sensor:      Sensor filter, e.g. "LISS-IV", "AWiFS".
            max_results: Maximum number of scenes to return.

        Returns:
            BhoonidhiSearchResult or BhoonidhiUnavailableResult.
        """
        if not self.is_configured():
            return self.unavailable_result()

        if not self._authenticate():
            return self.unavailable_result("Bhoonidhi authentication failed — check credentials.")

        try:
            import requests

            query: Dict[str, Any] = {
                "bbox": bbox,
                "datetime": f"{date_range[0]}/{date_range[1]}",
                "limit": max_results,
            }
            if sensor:
                query["collections"] = [sensor]

            resp = requests.post(
                SEARCH_ENDPOINT,
                json=query,
                headers=self._auth_headers(),
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()

        except Exception as exc:
            logger.warning("Bhoonidhi STAC search failed: %s", exc)
            return BhoonidhiSearchResult(
                available=True,
                scenes=[],
                total_found=0,
                message=f"Search request failed: {exc}",
                warnings=[str(exc)],
            )

        # Parse STAC Feature Collection
        features = data.get("features", [])
        scenes: List[BhoonidhiScene] = []
        warnings: List[str] = []

        for feat in features:
            try:
                props = feat.get("properties", {})
                scene = BhoonidhiScene(
                    product_id=feat.get("id", "unknown"),
                    sensor=props.get("platform") or props.get("sensor") or "Unknown",
                    acquisition_date=props.get("datetime", "Unknown"),
                    bbox=feat.get("bbox", []),
                    cloud_cover_pct=props.get("eo:cloud_cover"),
                    download_url=self._extract_download_url(feat),
                    raw_stac=feat,
                )
                scenes.append(scene)
            except Exception as exc:
                warnings.append(f"Failed to parse scene feature: {exc}")

        return BhoonidhiSearchResult(
            available=True,
            scenes=scenes,
            total_found=data.get("numberMatched", len(scenes)),
            query_bbox=bbox,
            query_date_range=f"{date_range[0]}/{date_range[1]}",
            query_sensor=sensor,
            message=f"Found {len(scenes)} scene(s).",
            warnings=warnings,
        )

    @staticmethod
    def _extract_download_url(feature: Dict) -> Optional[str]:
        """Extract a download URL from a STAC feature, if present."""
        links = feature.get("links", [])
        for link in links:
            if link.get("rel") in ("download", "data", "enclosure"):
                return link.get("href")
        assets = feature.get("assets", {})
        for key in ("data", "download", "product"):
            if key in assets:
                return assets[key].get("href")
        return None

    # ── Download (requires explicit caller approval) ───────────────────────────

    def download_scene(
        self,
        scene: BhoonidhiScene,
        output_dir: str,
        max_size_mb: float = 500.0,
    ) -> Dict[str, Any]:
        """
        Download a single scene to output_dir.

        Does NOT download automatically — the caller must explicitly call this.
        Refuses to download if the estimated file size exceeds max_size_mb.

        Returns a dict with:
          {
            "success": bool,
            "filepath": str or None,
            "size_mb": float or None,
            "message": str,
          }
        """
        if not self.is_configured():
            return {"success": False, "filepath": None, "size_mb": None,
                    "message": "Bhoonidhi not configured."}

        if not scene.download_url:
            return {"success": False, "filepath": None, "size_mb": None,
                    "message": f"No download URL available for scene {scene.product_id}."}

        if not self._authenticate():
            return {"success": False, "filepath": None, "size_mb": None,
                    "message": "Authentication failed."}

        try:
            import requests
            import os

            # HEAD request to check size before downloading
            head = requests.head(
                scene.download_url,
                headers=self._auth_headers(),
                timeout=10,
                allow_redirects=True,
            )
            content_length = head.headers.get("Content-Length")
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > max_size_mb:
                    return {
                        "success": False,
                        "filepath": None,
                        "size_mb": round(size_mb, 1),
                        "message": (
                            f"Scene size {size_mb:.0f} MB exceeds limit {max_size_mb:.0f} MB. "
                            f"Approval required before downloading."
                        ),
                    }
            else:
                size_mb = None

            # Download
            os.makedirs(output_dir, exist_ok=True)
            filename = os.path.join(output_dir, f"{scene.product_id}.tif")

            with requests.get(
                scene.download_url,
                headers=self._auth_headers(),
                stream=True,
                timeout=120,
            ) as resp:
                resp.raise_for_status()
                with open(filename, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)

            actual_size_mb = os.path.getsize(filename) / (1024 * 1024)
            logger.info("Downloaded %s → %s (%.1f MB)", scene.product_id, filename, actual_size_mb)

            return {
                "success": True,
                "filepath": filename,
                "size_mb": round(actual_size_mb, 1),
                "message": f"Downloaded {actual_size_mb:.1f} MB to {filename}.",
            }

        except Exception as exc:
            logger.error("Bhoonidhi download failed for %s: %s", scene.product_id, exc)
            return {
                "success": False,
                "filepath": None,
                "size_mb": None,
                "message": f"Download failed: {exc}",
            }


# ── Module-level singleton ────────────────────────────────────────────────────

_client: Optional[BhoonidhiClient] = None


def get_bhoonidhi_client() -> BhoonidhiClient:
    global _client
    if _client is None:
        _client = BhoonidhiClient()
    return _client
