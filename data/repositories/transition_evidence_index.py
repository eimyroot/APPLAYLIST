from __future__ import annotations

import hashlib
from collections.abc import Mapping

from data.connection import get_sqlite_connection
from data.repositories.music_intelligence_repository import MusicIntelligenceRepository

_MAX_RESULTS = 16


class TransitionEvidenceIndex:
    """Read-only metadata index over canonical persisted TransitionAssessment snapshots."""

    def __init__(self, *, repository: MusicIntelligenceRepository | None = None) -> None:
        self.repository = repository or MusicIntelligenceRepository()

    def list_pair_snapshots(
        self,
        *,
        source_track_id: str,
        target_track_id: str,
        limit: int = _MAX_RESULTS,
    ) -> tuple[dict[str, object], ...]:
        source = self._token(source_track_id)
        target = self._token(target_track_id)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= _MAX_RESULTS:
            raise ValueError("transition evidence limit must be 1..16")
        self.repository.ensure_schema()
        with get_sqlite_connection() as conn:
            rows = conn.execute(
                '''
                SELECT snapshot_id, transition_id, source_segment_id, target_segment_id,
                       assessment_version, policy_version, context_id, context_version,
                       payload_json, payload_sha256, created_at
                FROM transition_assessment_snapshots
                WHERE source_track_id = ? AND target_track_id = ?
                ORDER BY created_at DESC, snapshot_id DESC
                LIMIT ?
                ''',
                (source, target, limit),
            ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            payload = str(row["payload_json"])
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            expected = str(row["payload_sha256"])
            if digest != expected:
                raise RuntimeError("stored TransitionAssessment metadata failed integrity verification")
            result.append(
                {
                    "snapshot_id": str(row["snapshot_id"]),
                    "transition_id": str(row["transition_id"]),
                    "source_segment_id": str(row["source_segment_id"]),
                    "target_segment_id": str(row["target_segment_id"]),
                    "assessment_version": str(row["assessment_version"]),
                    "policy_version": str(row["policy_version"]),
                    "context_id": str(row["context_id"]),
                    "context_version": str(row["context_version"]),
                    "payload_sha256": expected,
                    "created_at": str(row["created_at"]),
                }
            )
        return tuple(result)

    @staticmethod
    def _token(value: str) -> str:
        if not isinstance(value, str) or not value or value.strip() != value or len(value) > 256:
            raise ValueError("invalid transition evidence track identity")
        if "/" in value or "\\" in value or any(ch.isspace() or ord(ch) < 32 for ch in value):
            raise ValueError("invalid transition evidence track identity")
        return value


__all__ = ["TransitionEvidenceIndex"]
