from types import MappingProxyType

import pytest

from core.config.composition_authority import (
    CompositionAuthorityName,
    resolve_composition_authority,
)
from data.models.playlist_candidate import PlaylistCandidate
from services.orchestrator.composition_authority import (
    CanonicalCompositionAuthority,
    LegacyCompositionAuthority,
    PipelineCompositionCommand,
    PipelineCompositionOutcome,
)
from services.orchestrator.pipeline import OrchestratorPipeline


class FakeComposer:
    def compose(self, limit: int) -> list[PlaylistCandidate]:
        return []


class FakeExporter:
    def export_m3u(self, *, playlist_id: str, tracks: list) -> dict:
        return {"playlist_id": playlist_id}


class ExplicitAuthority:
    authority_name = "custom"

    def execute(self, command: PipelineCompositionCommand) -> PipelineCompositionOutcome:
        track = PlaylistCandidate(
            track_id="explicit-1",
            path="/music/explicit-1.mp3",
            bpm=128.0,
            camelot="8A",
            energy=0.7,
        )
        return PipelineCompositionOutcome(
            run_id="explicit-run",
            tracks=(track,),
            export=MappingProxyType({"playlist_id": "explicit-run"}),
        )


def test_resolver_defaults_to_legacy_without_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COMPOSITION_AUTHORITY", raising=False)

    assert resolve_composition_authority() == CompositionAuthorityName.LEGACY


def test_default_pipeline_uses_legacy_authority(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COMPOSITION_AUTHORITY", raising=False)

    pipeline = OrchestratorPipeline(comparison_enabled=False)

    assert isinstance(pipeline._composition_authority, LegacyCompositionAuthority)
    assert pipeline.composer is not None
    assert pipeline.exporter is not None


def test_canonical_environment_selects_canonical_authority(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMPOSITION_AUTHORITY", "canonical")

    pipeline = OrchestratorPipeline(comparison_enabled=False)

    assert isinstance(pipeline._composition_authority, CanonicalCompositionAuthority)
    assert pipeline.composer is None
    assert pipeline.exporter is None


def test_invalid_environment_value_fails_configuration(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMPOSITION_AUTHORITY", "unsupported")

    with pytest.raises(ValueError):
        OrchestratorPipeline(comparison_enabled=False)


def test_explicit_legacy_dependencies_override_configured_canonical(monkeypatch) -> None:
    monkeypatch.setenv("COMPOSITION_AUTHORITY", "canonical")
    composer = FakeComposer()
    exporter = FakeExporter()

    pipeline = OrchestratorPipeline(
        composer=composer,
        exporter=exporter,
        run_id_factory=lambda: "pipeline-explicit",
        comparison_enabled=False,
    )

    assert isinstance(pipeline._composition_authority, LegacyCompositionAuthority)
    assert pipeline.composer is composer
    assert pipeline.exporter is exporter


def test_explicit_authority_is_not_overridden_by_configuration(monkeypatch) -> None:
    monkeypatch.setenv("COMPOSITION_AUTHORITY", "canonical")
    authority = ExplicitAuthority()

    pipeline = OrchestratorPipeline(
        composition_authority=authority,
        comparison_enabled=False,
    )

    assert pipeline._composition_authority is authority
    result = pipeline.run(path="/music", limit=1)
    assert result["tracks"] == ["explicit-1"]
    assert result["export"] == {"playlist_id": "explicit-run"}


def test_canonical_authority_rejects_comparison_observability(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMPOSITION_AUTHORITY", "canonical")

    with pytest.raises(ValueError, match="cannot be combined"):
        OrchestratorPipeline(
            comparison_enabled=True,
            comparison_hook=object(),
        )
