from __future__ import annotations

import hashlib
from pathlib import Path

from services.intelligence.real_library_pilot import analyze_real_tracks


class _FakeAnalyzer:
    provider_name = "fake-real-library-mir"

    def analyze(self, path: str) -> dict:
        return {
            "provider": self.provider_name,
            "provider_version": "test-provider-v1",
            "algorithm_version": "test-algorithm-v1",
            "bpm": 132.0,
            "bpm_confidence": 0.9,
            "camelot": "8A",
            "key_confidence": 0.8,
            "energy": 0.65,
            "loudness_db": -9.0,
            "duration_seconds": 240.0,
            "beat_stability": 0.8,
            "harmonic_ratio": 0.5,
            "percussive_ratio": 0.7,
            "warnings": [],
        }


def test_analyze_real_tracks_uses_byte_sha256_not_inventory_signature(tmp_path: Path) -> None:
    audio = tmp_path / "real-track.mp3"
    payload = b"verified-audio-content-for-real-library-pilot"
    audio.write_bytes(payload)
    content_sha256 = hashlib.sha256(payload).hexdigest()
    inventory_signature = "f" * 64
    track_id = "trk_real_identity_test"

    snapshot = {
        "schema": "applaylist-local-library-snapshot-r1",
        "snapshot_id": "snapshot-real-identity",
        "snapshot_version": "local-library-subset-r1",
        "library_fingerprint": "library-fingerprint",
        "created_date": "2026-08-17",
        "scope": {"kind": "REAL_INVENTORY_BACKED_SUBSET"},
        "privacy": {"publishable_to_public_repo": False},
        "tracks": [
            {
                "track_id": track_id,
                "absolute_path": str(audio),
                "file_signature": inventory_signature,
                "display_name": "Artist - Real Track",
                "artist": "Artist",
                "genre": "Techno",
                "energy": 6.5,
            },
            {
                "track_id": "trk_candidate_identity_test",
                "absolute_path": str(audio),
                "file_signature": "e" * 64,
                "display_name": "Artist - Candidate",
                "artist": "Artist",
                "genre": "Techno",
                "energy": 6.5,
            },
        ],
    }
    selection = {
        "schema": "applaylist-curated-case-selection-r1",
        "snapshot_ref": [snapshot["snapshot_id"], snapshot["snapshot_version"]],
        "case_specs": [
            {
                "case_spec_id": "case-real-identity",
                "set_role": "MID_SET",
                "seed_track_id": track_id,
                "candidate_scope_track_ids": ["trk_candidate_identity_test"],
            }
        ],
    }

    result = analyze_real_tracks(
        snapshot_raw=snapshot,
        selection_raw=selection,
        analyzer=_FakeAnalyzer(),  # type: ignore[arg-type]
    )

    evidence = result[track_id]
    assert evidence.content_sha256 == content_sha256
    assert evidence.source.file_signature == inventory_signature
    assert evidence.music_dna.identity.content_identity == f"sha256:{content_sha256}"
    assert evidence.music_dna.evidence.input_identity == f"sha256:{content_sha256}"
    assert content_sha256 != inventory_signature
