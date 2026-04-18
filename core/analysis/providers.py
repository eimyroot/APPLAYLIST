from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AnalyzerProviderInfo:
    name: str
    available: bool
    reason: str = ""


class BaseAnalyzerProvider:
    name = "base"

    @classmethod
    def is_available(cls) -> AnalyzerProviderInfo:
        return AnalyzerProviderInfo(name=cls.name, available=False, reason="not implemented")

    def analyze(self, path: str) -> Dict[str, Any]:
        raise NotImplementedError


class LibrosaAnalyzerProvider(BaseAnalyzerProvider):
    name = "librosa"

    @classmethod
    def is_available(cls) -> AnalyzerProviderInfo:
        spec = importlib.util.find_spec("librosa")
        if spec is None:
            return AnalyzerProviderInfo(name=cls.name, available=False, reason="librosa not installed")
        return AnalyzerProviderInfo(name=cls.name, available=True, reason="ok")

    def analyze(self, path: str) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "path": path,
            "status": "stub",
        }


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
            return AnalyzerProviderInfo(name=cls.name, available=True, reason="python essentia available")

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
    for cls in (LibrosaAnalyzerProvider, EssentiaAnalyzerProvider):
        info = cls.is_available()
        infos[cls.name] = info
    return infos


def select_best_provider(preferred: Optional[str] = None) -> BaseAnalyzerProvider:
    providers = {
        "librosa": LibrosaAnalyzerProvider,
        "essentia": EssentiaAnalyzerProvider,
    }

    if preferred:
        preferred = preferred.strip().lower()
        if preferred not in providers:
            raise ValueError(f"Unknown provider: {preferred}")
        info = providers[preferred].is_available()
        if not info.available:
            raise RuntimeError(f"Preferred provider unavailable: {preferred} ({info.reason})")
        return providers[preferred]()

    for name in ("librosa", "essentia"):
        info = providers[name].is_available()
        if info.available:
            return providers[name]()

    raise RuntimeError("No analyzer provider available")
