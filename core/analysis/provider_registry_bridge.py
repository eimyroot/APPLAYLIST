from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.analysis.provider_contracts import ProviderAvailability
from core.analysis.provider_selection import ProviderSelectionResult, select_provider


@dataclass(frozen=True)
class ProviderRegistrySelectionConfig:
    requested_provider: str | None = None
    configured_default: str | None = None
    safe_baseline: str = "baseline"


def select_from_registry_availability(
    *,
    config: ProviderRegistrySelectionConfig,
    availability: Iterable[ProviderAvailability],
) -> ProviderSelectionResult:
    """Bridge provider registry metadata to provider selection policy.

    This module intentionally does not import provider implementations.
    It only accepts availability metadata produced elsewhere.

    That keeps API startup safe from optional audio dependencies such as:
    - librosa
    - numba
    - llvmlite
    - essentia
    """

    return select_provider(
        requested_provider=config.requested_provider,
        configured_default=config.configured_default,
        safe_baseline=config.safe_baseline,
        availability=availability,
    )
