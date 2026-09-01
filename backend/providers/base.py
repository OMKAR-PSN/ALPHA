"""
SatQuery AI — Base Provider Interface

All reconstruction/heavy-model providers implement this ABC.
The rest of SatQuery does not need to know whether the model runs:
  - on this CPU (CPUInpaintingProvider)
  - on a remote GPU (RemoteGPUProvider)
  - as a precomputed demo asset (PrecomputedProvider)

Adding a new provider in the future requires only:
  1. Subclass BaseProvider
  2. Implement reconstruct() and is_available()
  3. Register in provider_factory.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from backend.schemas.provenance import ExecutionMode, InputProvenance


@dataclass
class ProviderResult:
    """Standardised output from any reconstruction provider."""

    output_b64: str
    """Base64-encoded PNG of the reconstructed/processed image."""

    execution_mode: ExecutionMode
    algorithm: str
    input_provenance: InputProvenance

    success: bool = True
    message: str = ""

    runtime_ms: Optional[int] = None
    """Actual wall-clock time in milliseconds, if measured."""

    model_id: Optional[str] = None
    """Identifier of the model or script used (e.g. 'EMRDM-SEN12MS-CR')."""

    checkpoint: Optional[str] = None
    """Checkpoint filename, if applicable."""

    warnings: list = field(default_factory=list)


class BaseProvider(ABC):
    """
    Abstract interface for all heavy-computation providers.

    Design contract:
      - is_available() MUST be called before reconstruct().
      - reconstruct() MUST NOT be called on an arbitrary user image
        when execution_mode == PRECOMPUTED_MODEL_OUTPUT.
      - Implementations must NOT return a cached result for a
        scene_id that does not match the input exactly.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True iff this provider can currently serve requests."""
        ...

    @abstractmethod
    def reconstruct(
        self,
        image_b64: str,
        mask_b64: str,
        scene_id: Optional[str] = None,
        input_provenance: InputProvenance = InputProvenance.UNKNOWN,
    ) -> ProviderResult:
        """
        Reconstruct cloud-obscured pixels.

        Args:
            image_b64:  Base64 PNG of the cloudy input image.
            mask_b64:   Base64 PNG of the binary cloud mask (white=cloud).
            scene_id:   Identifier of a predefined demo scene, or None for
                        user-uploaded images (which must never receive
                        precomputed outputs).
            input_provenance: Origin of the input image.

        Returns:
            ProviderResult with output_b64 and provenance metadata.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""
        ...
