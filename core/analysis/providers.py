from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.analysis.provider_contract import (
    ProviderContractError,
    ProviderDependencyMissingError,
    ProviderRuntimeFailure,
    ProviderUnavailableError,
    UnknownProviderError,
)


@dataclass(frozen=True)
class AnalyzerProviderInfo:
    name: str
    available: bool
    reason: str = ""


class BaseAnalyzerProvider:
    name = "base"

    @classmethod
    def is_available(cls) -> AnalyzerProviderInfo:
        return AnalyzerProviderInfo(
            name=cls.name,
            available=False,
            reason="not implemented",
        )

    def analyze(self, path: str) -> Dict[str, Any]:
        raise NotImplementedError


class LibrosaAnalyzerProvider(BaseAnalyzerProvider):
    name = "librosa"

    @classmethod
    def is_available(cls) -> AnalyzerProviderInfo:
        spec = importlib.util.find_spec("librosa")
        if spec is None:
            return AnalyzerProviderInfo(
                name=cls.name,
                available=False,
                reason="librosa not installed",
            )
        return AnalyzerProviderInfo(name=cls.name, available=True, reason="ok")

    def analyze(self, path: str) -> Dict[str, Any]:
        try:
            from services.analysis.librosa_baseline import BaselineLibrosaMIR

            return BaselineLibrosaMIR().analyze(path)
        except ProviderContractError:
            raise
        except Exception as exc:
            raise ProviderRuntimeFailure(
                "Librosa baseline analysis failed",
                provider=self.name,
            ) from exc


class EssentiaAnalyzerProvider(BaseAnalyzerProvider):
    name = "essentia"

    @classmethod
    def is_available(cls) -> AnalyzerProviderInfo:
        if os.getenv("APPLAYLIST_ENABLE_ESSENTIA", "0") != "1":
            return AnalyzerProviderInfo(
                name=cls.name,
                available=False,
                reason="disabled by env APPLAYLIST_ENABLE_ESSENTIA!=1",
            )

        py_spec = importlib.util.find_spec("essentia")
        if py_spec is not None:
            return AnalyzerProviderInfo(
                name=cls.name,
                available=True,
                reason="python essentia available",
            )

        return AnalyzerProviderInfo(
            name=cls.name,
            available=False,
            reason="essentia not installed",
        )

    def analyze(self, path: str) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "path": path,
            "status": "stub",
        }


def list_analyzer_providers() -> Dict[str, AnalyzerProviderInfo]:
    infos = {}
    for provider_class in (LibrosaAnalyzerProvider, EssentiaAnalyzerProvider):
        info = provider_class.is_available()
        infos[provider_class.name] = info
    return infos


def _raise_unavailable(info: AnalyzerProviderInfo) -> None:
    message = f"Preferred provider unavailable: {info.name} ({info.reason})"
    if info.reason.endswith("not installed"):
        raise ProviderDependencyMissingError(message, provider=info.name)
    raise ProviderUnavailableError(message, provider=info.name)


def select_best_provider(preferred: Optional[str] = None) -> BaseAnalyzerProvider:
    providers = {
        "librosa": LibrosaAnalyzerProvider,
        "essentia": EssentiaAnalyzerProvider,
    }

    if preferred:
        normalized = preferred.strip().lower()
        if normalized not in providers:
            raise UnknownProviderError(
                f"Unknown provider: {normalized}",
                provider=normalized,
            )
        info = providers[normalized].is_available()
        if not info.available:
            _raise_unavailable(info)
        return providers[normalized]()

    for name in ("librosa", "essentia"):
        info = providers[name].is_available()
        if info.available:
            return providers[name]()

    raise ProviderUnavailableError("No analyzer provider available")
