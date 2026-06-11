from __future__ import annotations

import importlib
import sys


OPTIONAL_AUDIO_MODULES = {
    "librosa",
    "numba",
    "llvmlite",
    "essentia",
}


def test_baseline_provider_import_does_not_force_audio_analyzer_stack() -> None:
    before = set(sys.modules)

    module = importlib.import_module("core.analysis.provider_baseline")

    after = set(sys.modules)
    newly_imported = after - before

    assert module.get_baseline_provider_metadata().name == "baseline"
    assert OPTIONAL_AUDIO_MODULES.intersection(newly_imported) == set()
