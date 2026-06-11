from __future__ import annotations

import importlib
import sys

from core.analysis import provider_registry


OPTIONAL_AUDIO_MODULES = {
    "librosa",
    "numba",
    "llvmlite",
    "essentia",
}


def test_registry_exposes_baseline_metadata() -> None:
    metadata = provider_registry.get_provider_metadata(["baseline"])[0]

    assert metadata.name == "baseline"
    assert metadata.backend == "audio-analyzer"
    assert metadata.optional_dependencies == ()
    assert "bpm" in metadata.capabilities


def test_registry_exposes_advanced_provider_metadata_without_importing_provider() -> None:
    metadata = provider_registry.get_provider_metadata(["librosa", "essentia"])

    by_name = {item.name: item for item in metadata}

    assert by_name["librosa"].backend == "librosa"
    assert "librosa" in by_name["librosa"].optional_dependencies
    assert by_name["essentia"].backend == "essentia"
    assert by_name["essentia"].optional_dependencies == ("essentia",)


def test_registry_metadata_import_does_not_force_optional_audio_stack() -> None:
    before = set(sys.modules)

    importlib.import_module("core.analysis.provider_registry")
    provider_registry.get_provider_metadata(["baseline", "librosa", "essentia"])

    after = set(sys.modules)
    newly_imported = after - before

    assert OPTIONAL_AUDIO_MODULES.intersection(newly_imported) == set()
