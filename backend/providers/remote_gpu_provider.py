"""
SatQuery AI — Remote GPU Provider (Stub)

This provider delegates inference to a remote GPU API endpoint.
It is NOT implemented yet — the class exists so the rest of SatQuery
can switch to a GPU backend without code changes elsewhere.

To activate:
  1. Set environment variable: SATQUERY_GPU_ENDPOINT=http://<host>:<port>
  2. Optionally set SATQUERY_GPU_API_KEY for bearer auth
  3. The endpoint must accept POST /predict with:
       {
         "image_b64": "<base64 PNG>",
         "mask_b64": "<base64 PNG>",
         "scene_id": "<optional>",
         "task": "cloud_reconstruction"
       }
     and return:
       {
         "output_b64": "<base64 PNG>",
         "model_id": "<string>",
         "runtime_ms": <int>,
         "algorithm": "<string>",
         "warnings": [...]
       }

Until the endpoint is configured, is_available() returns False
and reconstruct() raises NotImplementedError.
"""

import os
from typing import Optional

from backend.providers.base import BaseProvider, ProviderResult
from backend.schemas.provenance import ExecutionMode, InputProvenance


class RemoteGPUProvider(BaseProvider):
    """
    Delegates to a remote GPU inference API.
    Not implemented until SATQUERY_GPU_ENDPOINT is configured.
    """

    @property
    def name(self) -> str:
        return "RemoteGPUProvider"

    def is_available(self) -> bool:
        endpoint = os.environ.get("SATQUERY_GPU_ENDPOINT", "").strip()
        return bool(endpoint)

    def reconstruct(
        self,
        image_b64: str,
        mask_b64: str,
        scene_id: Optional[str] = None,
        input_provenance: InputProvenance = InputProvenance.UNKNOWN,
    ) -> ProviderResult:
        import requests

        endpoint = os.environ.get("SATQUERY_GPU_ENDPOINT", "").rstrip("/")
        api_key = os.environ.get("SATQUERY_GPU_API_KEY", "")

        if not endpoint:
            raise RuntimeError(
                "RemoteGPUProvider: SATQUERY_GPU_ENDPOINT not configured. "
                "Set the environment variable to enable GPU inference."
            )

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "image_b64": image_b64,
            "mask_b64": mask_b64,
            "scene_id": scene_id,
            "task": "cloud_reconstruction",
        }

        try:
            resp = requests.post(
                f"{endpoint}/predict",
                json=payload,
                headers=headers,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return ProviderResult(
                output_b64="",
                execution_mode=ExecutionMode.REMOTE_MODEL,
                algorithm="unknown",
                input_provenance=input_provenance,
                success=False,
                message=f"Remote GPU request failed: {exc}",
                warnings=[str(exc)],
            )

        return ProviderResult(
            output_b64=data.get("output_b64", ""),
            execution_mode=ExecutionMode.REMOTE_MODEL,
            algorithm=data.get("algorithm", "remote_model"),
            input_provenance=input_provenance,
            success=True,
            message="Remote GPU inference complete.",
            runtime_ms=data.get("runtime_ms"),
            model_id=data.get("model_id"),
            checkpoint=None,
            warnings=data.get("warnings", []),
        )
