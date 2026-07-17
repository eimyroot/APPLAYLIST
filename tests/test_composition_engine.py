from services.composition import (
    CompositionConstraints,
    CompositionFailureReason,
    CompositionMode,
    CompositionRequest,
    CompositionStatus,
    CompositionTrack,
    DeterministicCompositionEngine,
    EnergyStage,
)
from services.composition.scoring import score_transition


def _track(
    track_id: str,
    *,
    bpm: float,
    camelot: str,
    energy: float,
    artist: str | None = None,
    label: str | None = None,
    source: str | None = None,
    genre: str = "tech house",
    path: str | None = None,
) -> CompositionTrack:
    return CompositionTrack(
        track_id=track_id,
        path=path or f"/music/{track_id}.mp3",
        bpm=bpm,
        camelot=camelot,
        energy=energy,
        duration_seconds=300,
        genre=genre,
        artist=artist,
        label=label,
        source_folder=source,
    )


def test_engine_is_deterministic_and_input_order_independent() -> None:
    tracks = (
        _track("a", bpm=124, camelot="8A", energy=0.24, artist="A"),
        _track("b", bpm=125, camelot="9A", energy=0.48, artist="B"),
        _track("c", bpm=126, camelot="9A", energy=0.68, artist="C"),
        _track("d", bpm=127, camelot="10A", energy=0.86, artist="D"),
    )
    engine = DeterministicCompositionEngine()

    forward = engine.compose(
        CompositionRequest(
            tracks=tracks,
            target_track_count=4,
            mode=CompositionMode.FESTIVAL,
        )
    )
    reverse = engine.compose(
        CompositionRequest(
            tracks=tuple(reversed(tracks)),
            target_track_count=4,
            mode=CompositionMode.FESTIVAL,
        )
    )

    assert forward.status == CompositionStatus.SUCCESS
    assert [track.track_id for track in forward.tracks] == ["a", "b", "c", "d"]
    assert [track.track_id for track in reverse.tracks] == ["a", "b", "c", "d"]
    assert forward.decisions == reverse.decisions
    assert forward.summary.track_count == 4
    assert forward.summary.total_duration_seconds == 1200


def test_bpm_hard_gate_returns_controlled_partial_result() -> None:
    result = DeterministicCompositionEngine().compose(
        CompositionRequest(
            tracks=(
                _track("opening", bpm=120, camelot="8A", energy=0.25),
                _track("jump", bpm=130, camelot="9A", energy=0.50),
            ),
            target_track_count=2,
            mode=CompositionMode.CLUB,
        )
    )

    assert result.status == CompositionStatus.PARTIAL
    assert result.failure_reason == CompositionFailureReason.COMPOSITION_STALLED
    assert [track.track_id for track in result.tracks] == ["opening"]
    assert any("BPM hard gate" in warning for warning in result.warnings)


def test_start_key_selects_matching_opening_track() -> None:
    result = DeterministicCompositionEngine().compose(
        CompositionRequest(
            tracks=(
                _track("default", bpm=124, camelot="8A", energy=0.25),
                _track("keyed", bpm=126, camelot="5B", energy=0.30),
            ),
            target_track_count=1,
            start_key=" 5b ",
        )
    )

    assert result.status == CompositionStatus.SUCCESS
    assert result.tracks[0].track_id == "keyed"


def test_spacing_rules_change_selection_and_remain_explainable() -> None:
    opening = _track(
        "opening",
        bpm=124,
        camelot="8A",
        energy=0.25,
        artist="Same Artist",
        label="Same Label",
        source="same-source",
    )
    same = _track(
        "a-same",
        bpm=125,
        camelot="9A",
        energy=0.68,
        artist="Same Artist",
        label="Same Label",
        source="same-source",
    )
    alternative = _track(
        "z-alternative",
        bpm=125,
        camelot="9A",
        energy=0.68,
        artist="Other Artist",
        label="Other Label",
        source="other-source",
    )
    request = CompositionRequest(
        tracks=(opening, same, alternative),
        target_track_count=2,
        mode=CompositionMode.CLUB,
        constraints=CompositionConstraints(
            same_artist_min_gap=3,
            same_label_min_gap=2,
            same_source_folder_max_consecutive=1,
        ),
    )

    result = DeterministicCompositionEngine().compose(request)
    rejected_score = score_transition(
        current=opening,
        candidate=same,
        playlist=[opening],
        stage=EnergyStage.LIFT,
        request=request,
    )

    assert [track.track_id for track in result.tracks] == [
        "opening",
        "z-alternative",
    ]
    assert not rejected_score.artist_spacing_ok
    assert not rejected_score.label_spacing_ok
    assert not rejected_score.source_rotation_ok
    assert {
        reason.code for reason in result.decisions[1].score.reasons
    } >= {
        "bpm_flow",
        "harmonic_compatibility",
        "energy_target",
        "artist_spacing",
        "label_spacing",
        "source_rotation",
    }


def test_duplicate_track_ids_are_removed_deterministically() -> None:
    result = DeterministicCompositionEngine().compose(
        CompositionRequest(
            tracks=(
                _track(
                    "duplicate",
                    bpm=124,
                    camelot="8A",
                    energy=0.25,
                    path="/music/z.mp3",
                ),
                _track(
                    "duplicate",
                    bpm=124,
                    camelot="8A",
                    energy=0.25,
                    path="/music/a.mp3",
                ),
            ),
            target_track_count=1,
        )
    )

    assert result.tracks[0].path == "/music/a.mp3"
    assert any("duplicate track_id" in warning for warning in result.warnings)


def test_genre_filter_can_fail_without_side_effects() -> None:
    result = DeterministicCompositionEngine().compose(
        CompositionRequest(
            tracks=(
                _track(
                    "house",
                    bpm=124,
                    camelot="8A",
                    energy=0.25,
                    genre="house",
                ),
            ),
            target_track_count=1,
            genre="drum and bass",
        )
    )

    assert result.status == CompositionStatus.FAILED
    assert result.failure_reason == CompositionFailureReason.NO_CANDIDATES
    assert result.tracks == ()
    assert result.summary.track_count == 0
