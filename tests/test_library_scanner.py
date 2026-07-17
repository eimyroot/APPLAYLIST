from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.library import LibraryScanPolicy, SymlinkPolicy
from services.library import LibraryScanner


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"audio-candidate")
    return path.resolve()


def _symlink(target: Path, link: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")


def _codes(result) -> set[str]:
    return {issue.code for issue in (*result.skipped, *result.errors)}


def test_policy_normalizes_extensions_and_is_immutable() -> None:
    policy = LibraryScanPolicy(allowed_extensions=("MP3", ".Wav", "mp3"))

    assert policy.allowed_extensions == (".mp3", ".wav")
    with pytest.raises(FrozenInstanceError):
        policy.max_files = 1


@pytest.mark.parametrize("value", [True, 1.5, "10"])
def test_policy_rejects_non_integral_limits(value) -> None:
    with pytest.raises(TypeError):
        LibraryScanPolicy(max_files=value)


@pytest.mark.parametrize("value", [0, -1])
def test_policy_rejects_non_positive_limits(value: int) -> None:
    with pytest.raises(ValueError):
        LibraryScanPolicy(max_entries=value)


def test_scanner_rejects_relative_root() -> None:
    with pytest.raises(ValueError, match="absolute"):
        LibraryScanner().scan("relative/music")


def test_missing_and_file_roots_return_controlled_errors(tmp_path: Path) -> None:
    missing = LibraryScanner().scan(tmp_path / "missing")
    file_root = _touch(tmp_path / "single.mp3")
    not_directory = LibraryScanner().scan(file_root)

    assert missing.accepted_paths == ()
    assert [issue.code for issue in missing.errors] == ["root_not_found"]
    assert not_directory.accepted_paths == ()
    assert [issue.code for issue in not_directory.errors] == [
        "root_not_directory"
    ]


def test_recursive_scan_is_deterministic_and_evidenced(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    track_a = _touch(root / "a.wav")
    track_b = _touch(root / "B.MP3")
    nested_track = _touch(root / "nested" / "c.flac")
    _touch(root / "notes.txt")
    _touch(root / ".hidden.mp3")

    result = LibraryScanner().scan(root)

    assert result.accepted_paths == tuple(
        sorted(
            (str(track_a), str(track_b), str(nested_track)),
            key=lambda value: (value.casefold(), value),
        )
    )
    assert result.accepted_count == 3
    assert result.discovered_entries == 6
    assert result.complete is True
    assert {issue.code for issue in result.skipped} == {
        "hidden_entry_skipped",
        "unsupported_extension",
    }


def test_non_recursive_scan_does_not_descend(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    top_track = _touch(root / "top.mp3")
    _touch(root / "nested" / "deep.mp3")

    result = LibraryScanner(
        policy=LibraryScanPolicy(recursive=False)
    ).scan(root)

    assert result.accepted_paths == (str(top_track),)
    assert "directory_skipped_non_recursive" in _codes(result)


def test_entry_limit_stops_before_unbounded_traversal(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    first = _touch(root / "a.mp3")
    second = _touch(root / "b.mp3")
    _touch(root / "c.mp3")

    result = LibraryScanner(
        policy=LibraryScanPolicy(max_entries=2, max_files=10)
    ).scan(root)

    assert result.accepted_paths == (str(first), str(second))
    assert result.discovered_entries == 2
    assert result.entry_limit_reached is True
    assert result.file_limit_reached is False
    assert "entry_limit_reached" in _codes(result)


def test_file_limit_stops_on_next_supported_candidate(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    first = _touch(root / "a.mp3")
    _touch(root / "b.mp3")

    result = LibraryScanner(
        policy=LibraryScanPolicy(max_files=1)
    ).scan(root)

    assert result.accepted_paths == (str(first),)
    assert result.file_limit_reached is True
    assert result.entry_limit_reached is False
    assert "file_limit_reached" in _codes(result)


def test_cancellation_returns_explicit_partial_state(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    _touch(root / "a.mp3")
    calls = 0

    def cancel_requested() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 2

    result = LibraryScanner(cancel_requested=cancel_requested).scan(root)

    assert result.cancelled is True
    assert result.complete is False
    assert result.discovered_entries == 0
    assert result.accepted_paths == ()


def test_default_policy_skips_symlinks(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    target = _touch(root / "target.mp3")
    _symlink(target, root / "alias.mp3")

    result = LibraryScanner().scan(root)

    assert result.accepted_paths == (str(target),)
    assert "symlink_skipped" in _codes(result)


def test_allowed_symlink_inside_root_is_deduplicated(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    target = _touch(root / "target.mp3")
    _symlink(target, root / "alias.mp3")

    result = LibraryScanner(
        policy=LibraryScanPolicy(
            symlink_policy=SymlinkPolicy.ALLOW_WITHIN_ROOT
        )
    ).scan(root)

    assert result.accepted_paths == (str(target),)
    assert "duplicate_target" in _codes(result)


def test_allowed_symlink_cannot_escape_root(tmp_path: Path) -> None:
    root = (tmp_path / "library").resolve()
    root.mkdir()
    outside = _touch(tmp_path / "outside.mp3")
    _symlink(outside, root / "outside-link.mp3")

    result = LibraryScanner(
        policy=LibraryScanPolicy(
            symlink_policy=SymlinkPolicy.ALLOW_WITHIN_ROOT
        )
    ).scan(root)

    assert result.accepted_paths == ()
    assert "symlink_outside_root" in _codes(result)


def test_allowed_directory_symlink_cannot_create_loop(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    nested = root / "nested"
    track = _touch(nested / "track.mp3")
    _symlink(root, nested / "back", directory=True)

    result = LibraryScanner(
        policy=LibraryScanPolicy(
            symlink_policy=SymlinkPolicy.ALLOW_WITHIN_ROOT
        )
    ).scan(root)

    assert result.accepted_paths == (str(track),)
    assert result.entry_limit_reached is False
    assert "duplicate_directory" in _codes(result)
