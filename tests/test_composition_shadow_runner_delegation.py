import pytest

from services.composition import (
    CanonicalCompositionExecutionResult,
    CompositionResult,
    CompositionShadowService,
    CompositionStatus,
    CompositionSummary,
    CompositionTrack,
    ShadowComparisonRequest,
)


class RecordingRunner:
    def __init__(self) -> None:
        self.requests = []

    def run(self, request) -> CanonicalCompositionExecutionResult:
        self.requests.append(request)
        track = CompositionTrack(
            track_id="canonical-1",
            path="/music/canonical-1.mp3",
            bpm=128.0,
            camelot="8A",
            energy=0.6,
        )
        return CanonicalCompositionExecutionResult(
            composition=CompositionResult(
                status=CompositionStatus.SUCCESS,
                tracks=(track,),
                decisions=(),
                summary=CompositionSummary(
                    track_count=1,
                    total_duration_seconds=300,
                    average_bpm=128.0,
                    minimum_bpm=128.0,
                    maximum_bpm=128.0,
                    average_energy=0.6,
                ),
            ),
            candidate_count=4,
            adapted_count=3,
            rejected_count=1,
            fallback_count=1,
            adaptation_issues=(),
        )


def test_shadow_service_delegates_canonical_execution_to_runner() -> None:
    runner = RecordingRunner()
    service = CompositionShadowService(runner=runner)

    report = service.compare(
        ShadowComparisonRequest(
            legacy_track_ids=("canonical-1", "legacy-2"),
            target_track_count=3,
            bpm_min=124.0,
            bpm_max=132.0,
            mode="afterhours",
            genre="hypnotic techno",
            start_key="8A",
            duration_fallback_seconds=240,
        )
    )

    request = runner.requests[0]
    assert request.target_track_count == 3
    assert request.bpm_min == 124.0
    assert request.bpm_max == 132.0
    assert request.mode == "afterhours"
    assert request.genre == "hypnotic techno"
    assert request.start_key == "8A"
    assert request.duration_fallback_seconds == 240
    assert report.canonical_track_ids == ("canonical-1",)
    assert report.overlap_count == 1
    assert report.position_match_count == 1
    assert report.candidate_count == 4
    assert report.adapted_count == 3
    assert report.rejected_count == 1
    assert report.fallback_count == 1


def test_shadow_service_rejects_ambiguous_dependency_configuration() -> None:
    with pytest.raises(ValueError, match="runner cannot be combined"):
        CompositionShadowService(runner=RecordingRunner(), repository=object())
