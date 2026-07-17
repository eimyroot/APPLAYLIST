from __future__ import annotations

from dataclasses import dataclass

from core.config.composition_authority import (
    CompositionAuthorityName,
    resolve_composition_authority,
)
from core.config.settings import get_settings


class CompositionRuntimeConfigurationError(RuntimeError):
    """Raised when composition runtime settings are internally inconsistent."""


@dataclass(frozen=True, slots=True)
class CompositionRuntimeReadiness:
    status: str
    authority: CompositionAuthorityName
    comparison_enabled: bool
    receipts_enabled: bool

    def __post_init__(self) -> None:
        if self.status != "ready":
            raise ValueError("composition readiness status must be 'ready'")

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "composition_authority": self.authority.value,
            "composition_comparison_enabled": self.comparison_enabled,
            "composition_receipts_enabled": self.receipts_enabled,
        }


def evaluate_composition_runtime(
    *,
    authority: CompositionAuthorityName | str | None = None,
    comparison_enabled: bool | None = None,
    receipts_enabled: bool | None = None,
) -> CompositionRuntimeReadiness:
    try:
        resolved_authority = resolve_composition_authority(authority)
    except ValueError as exc:
        raise CompositionRuntimeConfigurationError(
            "invalid composition authority configuration"
        ) from exc

    if comparison_enabled is None or receipts_enabled is None:
        settings = get_settings()
        if comparison_enabled is None:
            comparison_enabled = settings.enable_composition_comparison
        if receipts_enabled is None:
            receipts_enabled = settings.enable_composition_receipts

    if not isinstance(comparison_enabled, bool) or not isinstance(receipts_enabled, bool):
        raise CompositionRuntimeConfigurationError(
            "composition observability settings must be boolean"
        )

    if receipts_enabled and not comparison_enabled:
        raise CompositionRuntimeConfigurationError(
            "composition receipts require composition comparison"
        )

    if resolved_authority == CompositionAuthorityName.CANONICAL and comparison_enabled:
        raise CompositionRuntimeConfigurationError(
            "canonical composition authority cannot be combined with comparison observability"
        )

    return CompositionRuntimeReadiness(
        status="ready",
        authority=resolved_authority,
        comparison_enabled=comparison_enabled,
        receipts_enabled=receipts_enabled,
    )
