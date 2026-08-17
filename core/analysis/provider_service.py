from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import metadata
from typing import Any, Protocol

from core.analysis.execution_identity import AnalysisExecutionIdentity
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

    def execution_identity(
        self,
        *,
        preferred_provider: str | None = None,
    ) -> AnalysisExecutionIdentity | None:
        """Return a pre-execution identity only when exact evidence reuse is safe.

        R1 intentionally enables reuse only for the versioned baseline librosa
        provider. Other providers remain fail-closed to fresh execution until they
        expose an equally stable pre-run identity contract.
        """

        provider = self._select_provider(preferred_provider)
        if provider.name != "librosa":
            return None
        try:
            from services.analysis.librosa_baseline import BaselineLibrosaMIR

            provider_version = metadata.version("librosa")
        except (ImportError, metadata.PackageNotFoundError):
            return None
        return AnalysisExecutionIdentity(
            provider=provider.name,
            analysis_version="canonical-mir-v1",
            provider_version=provider_version,
            algorithm_version=BaselineLibrosaMIR.algorithm_version,
        )

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
