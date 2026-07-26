from __future__ import annotations

from typing import Callable, Dict

from core.analysis.provider_essentia import analyze_with_essentia, essentia_available, essentia_enabled


def provider_capabilities() -> Dict[str, dict]:
    return {
        "essentia": {
            "enabled": essentia_enabled(),
            "available": essentia_available(),
            "canonical_mapping_ready": True,
            "extracts": ["bpm", "key", "energy", "lufs", "duration", "sample_rate"],
        }
    }


def provider_registry() -> Dict[str, Callable[[str], dict]]:
    registry: Dict[str, Callable[[str], dict]] = {}
    if essentia_enabled() and essentia_available():
        registry["essentia"] = analyze_with_essentia
    return registry

# --- APPLAYLIST PROVIDER AVAILABILITY METADATA ---

def _applaylist_optional_dependency_available(dependency: str) -> bool:
    """Return dependency visibility without importing the optional provider."""
    import importlib.util

    return importlib.util.find_spec(dependency) is not None


def get_provider_availability(provider_names=None):
    """Return runtime-safe provider availability metadata.

    This function must not import heavy optional audio stacks directly.
    It only checks dependency visibility via importlib.util.find_spec.
    """

    from core.analysis.provider_contracts import (
        ProviderAvailability,
        available,
        dependency_missing,
        unavailable,
    )

    known = ("baseline", "librosa", "essentia")
    names = tuple(provider_names) if provider_names is not None else known
    results: list[ProviderAvailability] = []

    for name in names:
        if name == "baseline":
            results.append(available("baseline"))
        elif name == "librosa":
            if _applaylist_optional_dependency_available("librosa"):
                results.append(available("librosa"))
            else:
                results.append(dependency_missing("librosa", "librosa"))
        elif name == "essentia":
            if _applaylist_optional_dependency_available("essentia"):
                results.append(available("essentia"))
            else:
                results.append(dependency_missing("essentia", "essentia"))
        else:
            results.append(unavailable(name, "unknown provider"))

    return results


def select_available_provider(
    *,
    requested_provider=None,
    configured_default=None,
    safe_baseline="baseline",
    provider_names=None,
):
    """Select a provider using registry availability metadata."""

    from core.analysis.provider_registry_bridge import (
        ProviderRegistrySelectionConfig,
        select_from_registry_availability,
    )

    return select_from_registry_availability(
        config=ProviderRegistrySelectionConfig(
            requested_provider=requested_provider,
            configured_default=configured_default,
            safe_baseline=safe_baseline,
        ),
        availability=get_provider_availability(provider_names),
    )


# --- APPLAYLIST PROVIDER METADATA REGISTRY ---

def get_provider_metadata(provider_names=None):
    """Return runtime-safe provider metadata.

    This function must not import provider implementations that pull heavy
    optional audio stacks into API startup.
    """

    from core.analysis.provider_baseline import get_baseline_provider_metadata
    from core.analysis.provider_contracts import ProviderMetadata

    known_names = ("baseline", "librosa", "essentia")
    names = tuple(provider_names) if provider_names is not None else known_names
    metadata: list[ProviderMetadata] = []

    for name in names:
        if name == "baseline":
            metadata.append(get_baseline_provider_metadata())
        elif name == "librosa":
            metadata.append(
                ProviderMetadata(
                    name="librosa",
                    version="0.1.0",
                    backend="librosa",
                    capabilities=("bpm", "key", "camelot", "energy", "loudness"),
                    optional_dependencies=("librosa", "numba", "llvmlite"),
                )
            )
        elif name == "essentia":
            metadata.append(
                ProviderMetadata(
                    name="essentia",
                    version="0.1.0",
                    backend="essentia",
                    capabilities=("bpm", "key", "camelot", "energy", "loudness"),
                    optional_dependencies=("essentia",),
                )
            )

    return metadata
