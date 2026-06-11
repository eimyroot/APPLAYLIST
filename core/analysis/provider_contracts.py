from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable


ProviderCapability = Literal[
    "bpm",
    "key",
    "camelot",
    "energy",
    "loudness",
    "structure",
    "embeddings",
]


ProviderStatus = Literal[
    "available",
    "unavailable",
    "dependency_missing",
    "disabled",
]


@dataclass(frozen=True)
class ProviderMetadata:
    name: str
    version: str
    backend: str
    capabilities: tuple[ProviderCapability, ...] = field(default_factory=tuple)
    optional_dependencies: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProviderAvailability:
    provider: str
    status: ProviderStatus
    reason: str | None = None

    @property
    def is_available(self) -> bool:
        return self.status == "available"


@dataclass(frozen=True)
class ProviderInput:
    track_id: str
    path: Path


@dataclass(frozen=True)
class ProviderOutput:
    provider: str
    backend: str
    raw: dict[str, Any]
    normalized: dict[str, Any]


@runtime_checkable
class AnalysisProvider(Protocol):
    metadata: ProviderMetadata

    def availability(self) -> ProviderAvailability:
        ...

    def analyze(self, provider_input: ProviderInput) -> ProviderOutput:
        ...


def unavailable(provider: str, reason: str) -> ProviderAvailability:
    return ProviderAvailability(provider=provider, status="unavailable", reason=reason)


def dependency_missing(provider: str, dependency: str) -> ProviderAvailability:
    return ProviderAvailability(
        provider=provider,
        status="dependency_missing",
        reason=f"Missing optional dependency: {dependency}",
    )


def available(provider: str) -> ProviderAvailability:
    return ProviderAvailability(provider=provider, status="available", reason=None)
