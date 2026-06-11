from __future__ import annotations

from pathlib import Path

from core.analysis.provider_contracts import (
    ProviderAvailability,
    ProviderInput,
    ProviderMetadata,
    ProviderOutput,
    available,
    dependency_missing,
    unavailable,
)


def test_provider_metadata_keeps_optional_dependencies_as_metadata_only() -> None:
    metadata = ProviderMetadata(
        name="essentia",
        version="0.1.0",
        backend="essentia",
        capabilities=("bpm", "key", "energy"),
        optional_dependencies=("essentia",),
    )

    assert metadata.name == "essentia"
    assert metadata.backend == "essentia"
    assert metadata.optional_dependencies == ("essentia",)


def test_provider_availability_available_helper() -> None:
    status = available("baseline")

    assert isinstance(status, ProviderAvailability)
    assert status.provider == "baseline"
    assert status.status == "available"
    assert status.is_available is True


def test_provider_availability_dependency_missing_helper() -> None:
    status = dependency_missing("essentia", "essentia")

    assert status.provider == "essentia"
    assert status.status == "dependency_missing"
    assert status.is_available is False
    assert "essentia" in str(status.reason)


def test_provider_availability_unavailable_helper() -> None:
    status = unavailable("librosa", "disabled by config")

    assert status.provider == "librosa"
    assert status.status == "unavailable"
    assert status.is_available is False
    assert status.reason == "disabled by config"


def test_provider_input_output_shapes() -> None:
    provider_input = ProviderInput(track_id="track-1", path=Path("/tmp/example.wav"))

    provider_output = ProviderOutput(
        provider="baseline",
        backend="numpy-scipy",
        raw={"tempo": 128.0},
        normalized={"bpm": 128.0},
    )

    assert provider_input.track_id == "track-1"
    assert provider_output.normalized["bpm"] == 128.0
