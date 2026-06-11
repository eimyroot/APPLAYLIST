from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.analysis import provider_registry
from core.analysis.provider_baseline import create_baseline_provider
from core.analysis.provider_contracts import ProviderInput, ProviderOutput
from core.analysis.provider_errors import provider_unavailable


def analyze_with_provider_selection(
    *,
    track_id: str,
    path: str | Path,
    requested_provider: str | None = None,
    configured_default: str | None = None,
    safe_baseline: str = "baseline",
    provider_names: Iterable[str] | None = None,
) -> ProviderOutput:
    """Analyze an audio file through provider selection.

    Sidecar orchestration path.
    It does not replace the existing AudioAnalyzer/API behavior yet.
    """

    selected = provider_registry.select_available_provider(
        requested_provider=requested_provider,
        configured_default=configured_default,
        safe_baseline=safe_baseline,
        provider_names=provider_names,
    )

    if not selected.selected or selected.provider is None:
        raise provider_unavailable(
            "registry",
            f"No provider available: {selected.reason}",
        )

    provider_input = ProviderInput(
        track_id=track_id,
        path=Path(path),
    )

    if selected.provider == "baseline":
        return create_baseline_provider().analyze(provider_input)

    raise provider_unavailable(
        selected.provider,
        "Provider selected but adapter is not registered in orchestrator",
    )
