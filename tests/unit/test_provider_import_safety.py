from __future__ import annotations

import importlib
import sys


OPTIONAL_AUDIO_MODULES = {
    "librosa",
    "numba",
    "llvmlite",
    "essentia",
}


def test_core_analysis_modules_import_without_forcing_optional_audio_stack() -> None:
    before = set(sys.modules)

    importlib.import_module("core.analysis.normalize")
    importlib.import_module("core.analysis.provider_registry")

    after = set(sys.modules)
    newly_imported = after - before

    forced_optional_imports = OPTIONAL_AUDIO_MODULES.intersection(newly_imported)

    assert forced_optional_imports == set(), (
        "Core provider boot path imported optional audio dependencies: "
        f"{sorted(forced_optional_imports)}"
    )


def test_optional_essentia_provider_module_does_not_break_import() -> None:
    module = importlib.import_module("core.analysis.provider_essentia")

    assert module is not None
