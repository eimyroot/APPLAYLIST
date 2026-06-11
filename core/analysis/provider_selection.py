from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.analysis.provider_contracts import ProviderAvailability


@dataclass(frozen=True)
class ProviderSelectionResult:
    provider: str | None
    reason: str
    fallback_used: bool = False

    @property
    def selected(self) -> bool:
        return self.provider is not None


def select_provider(
    *,
    requested_provider: str | None,
    configured_default: str | None,
    safe_baseline: str,
    availability: Iterable[ProviderAvailability],
) -> ProviderSelectionResult:
    availability_by_name = {item.provider: item for item in availability}

    def is_available(name: str | None) -> bool:
        if not name:
            return False
        status = availability_by_name.get(name)
        return bool(status and status.is_available)

    if requested_provider and is_available(requested_provider):
        return ProviderSelectionResult(
            provider=requested_provider,
            reason="requested_provider_available",
            fallback_used=False,
        )

    if configured_default and is_available(configured_default):
        return ProviderSelectionResult(
            provider=configured_default,
            reason="configured_default_available",
            fallback_used=bool(requested_provider),
        )

    if is_available(safe_baseline):
        return ProviderSelectionResult(
            provider=safe_baseline,
            reason="safe_baseline_available",
            fallback_used=bool(requested_provider or configured_default),
        )

    return ProviderSelectionResult(
        provider=None,
        reason="no_provider_available",
        fallback_used=bool(requested_provider or configured_default),
    )
