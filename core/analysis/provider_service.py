from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

from core.analysis.provider_contract import (
    CanonicalAnalysisResult,
    ProviderContractError,
    ProviderOutputInvalid,
    ProviderRuntimeFailure,
    ProviderUnavailableError,
    UnknownProviderError,
    normalize_provider_result,
)
from core.analysis.providers import BaseAnalyzerProvider, select_best_provider


class AnalyzerProvider(Protocol):
    name: str

    def analyze(self, path: str) -> Mapping[str, Any]: ...


ProviderSelector = Callable[[str | None], BaseAnalyzerProvider]


class RoutedAnalysisService:
    """Run one provider and return only a validated canonical result."""

    def __init__(self, selector: ProviderSelector = select_best_provider) -> None:
        self._selector = selector

    def analyze_path(
        self,
        path: str,
        *,
        preferred_provider: str | None = None,
    ) -> CanonicalAnalysisResult:
        if not isinstance(path, str) or not path.strip():
            raise ProviderOutputInvalid("Analysis path must be a non-empty string")

        provider = self._select_provider(preferred_provider)
        try:
            raw_result = provider.analyze(path)
        except ProviderContractError:
            raise
        except Exception as exc:
            raise ProviderRuntimeFailure(
                "Provider execution failed",
                provider=provider.name,
            ) from exc

        return normalize_provider_result(
            raw_result,
            path=path,
            expected_provider=provider.name,
        )

    def _select_provider(self, preferred_provider: str | None) -> AnalyzerProvider:
        try:
            return self._selector(preferred_provider)
        except (UnknownProviderError, ProviderUnavailableError):
            raise
        except ValueError as exc:
            raise UnknownProviderError(
                str(exc),
                provider=preferred_provider,
            ) from exc
        except RuntimeError as exc:
            raise ProviderUnavailableError(
                str(exc),
                provider=preferred_provider,
            ) from exc
        except Exception as exc:
            raise ProviderUnavailableError(
                "Provider selection failed",
                provider=preferred_provider,
            ) from exc
