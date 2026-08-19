from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository
from data.repositories.playlist_revision_repository import PlaylistRevisionRepository
from data.repositories.transition_evidence_index import TransitionEvidenceIndex
from services.desktop.playlist_export_transport import (
    DesktopPlaylistExportTransport,
    DesktopPlaylistExportTransportError,
)

_MAX_JSON_BYTES = 256 * 1024
_PREVIEW_SCHEMA = "applaylist-desktop-playlist-evidence-preview-r1"
_MATERIAL_SCHEMA = "applaylist-desktop-playlist-evidence-material-r1"
_DOCUMENT_SCHEMA = "applaylist-playlist-revision-evidence-r1"
_FORMAT = "json"


class DesktopPlaylistEvidenceExportError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DesktopPlaylistEvidenceExportTransport:
    """Deterministic evidence companion for one exact immutable PlaylistRevision."""

    def __init__(
        self,
        *,
        revisions: PlaylistRevisionRepository | None = None,
        analysis: AnalysisEvidenceRepository | None = None,
        transitions: TransitionEvidenceIndex | None = None,
        m3u8: DesktopPlaylistExportTransport | None = None,
    ) -> None:
        self.revisions = revisions or PlaylistRevisionRepository()
        self.analysis = analysis or AnalysisEvidenceRepository()
        self.transitions = transitions or TransitionEvidenceIndex()
        self.m3u8 = m3u8 or DesktopPlaylistExportTransport(revisions=self.revisions)

    def preview(self, *, revision_id: str) -> dict[str, object]:
        document, verification = self._document(revision_id)
        tracks = document["tracks"]
        transitions = document["adjacent_transitions"]
        assert isinstance(tracks, list)
        assert isinstance(transitions, list)
        return {
            "schema": _PREVIEW_SCHEMA,
            "revision_id": document["revision"]["revision_id"],
            "playlist_id": document["revision"]["playlist_id"],
            "revision_index": document["revision"]["revision_index"],
            "format": _FORMAT,
            "suggested_filename": self._suggested_filename(str(document["revision"]["revision_id"])),
            "track_count": len(tracks),
            "analysis_evidence_count": sum(1 for item in tracks if item["analysis"]["status"] == "present"),
            "transition_pair_count": len(transitions),
            "transition_evidence_pair_count": sum(1 for item in transitions if item["status"] == "present"),
            "m3u8_path_valid": verification["path_valid"],
            "m3u8_content_sha256": verification["content_sha256"],
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
        }

    def material(self, *, revision_id: str) -> dict[str, object]:
        document, verification = self._document(revision_id)
        content = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ) + "\n"
        encoded = content.encode("utf-8")
        if len(encoded) > _MAX_JSON_BYTES:
            raise DesktopPlaylistEvidenceExportError(
                "playlist_evidence_export_too_large",
                "The JSON evidence export exceeds the bounded size limit.",
            )
        digest = hashlib.sha256(encoded).hexdigest()
        revision = document["revision"]
        return {
            "schema": _MATERIAL_SCHEMA,
            "revision_id": revision["revision_id"],
            "playlist_id": revision["playlist_id"],
            "revision_index": revision["revision_index"],
            "format": _FORMAT,
            "suggested_filename": self._suggested_filename(str(revision["revision_id"])),
            "track_count": len(document["tracks"]),
            "m3u8_path_valid": verification["path_valid"],
            "m3u8_content_sha256": verification["content_sha256"],
            "content_utf8": content,
            "content_sha256": digest,
            "byte_count": len(encoded),
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
        }

    def _document(self, revision_id: str) -> tuple[dict[str, object], dict[str, object]]:
        revision = self._revision(revision_id)
        items = self._items(revision)
        try:
            m3u8 = self.m3u8.material(revision_id=str(revision["revision_id"]))
        except DesktopPlaylistExportTransportError as exc:
            raise DesktopPlaylistEvidenceExportError(exc.code, exc.message) from exc
        verification = {
            "path_valid": True,
            "format": "m3u8",
            "track_count": int(m3u8["track_count"]),
            "content_sha256": str(m3u8["content_sha256"]),
            "byte_count": int(m3u8["byte_count"]),
        }
        tracks: list[dict[str, object]] = []
        for item in items:
            track_id = str(item["track_id"])
            evidence = self.analysis.latest_success_for_track(track_id)
            if evidence is None:
                analysis: dict[str, object] = {"status": "missing"}
            else:
                correction = self.analysis.latest_active_correction(track_id, evidence.evidence_id)
                analysis = {
                    "status": "present",
                    "evidence_id": evidence.evidence_id,
                    "provider": evidence.provider,
                    "analysis_version": evidence.analysis_version,
                    "provider_version": evidence.provider_version,
                    "algorithm_version": evidence.algorithm_version,
                    "bpm": evidence.bpm,
                    "bpm_confidence": evidence.bpm_confidence,
                    "key_tonic": evidence.key_tonic,
                    "key_scale": evidence.key_scale,
                    "camelot": evidence.camelot,
                    "key_confidence": evidence.key_confidence,
                    "energy": evidence.energy,
                    "loudness_db": evidence.loudness_db,
                    "duration_seconds": evidence.duration_seconds,
                    "warnings": list(evidence.warnings),
                    "created_at": evidence.created_at,
                    "active_correction": (
                        None
                        if correction is None
                        else {
                            "correction_id": correction.correction_id,
                            "base_evidence_id": correction.base_evidence_id,
                            "payload": json.loads(correction.payload_json),
                            "reason": correction.reason,
                            "created_at": correction.created_at,
                        }
                    ),
                }
            tracks.append(
                {
                    "order_index": int(item["order_index"]),
                    "track_id": track_id,
                    "display_name": str(item["display_name"]),
                    "locked": bool(item["locked"]),
                    "analysis": analysis,
                }
            )

        adjacent: list[dict[str, object]] = []
        for index in range(len(items) - 1):
            source = str(items[index]["track_id"])
            target = str(items[index + 1]["track_id"])
            snapshots = self.transitions.list_pair_snapshots(
                source_track_id=source,
                target_track_id=target,
            )
            adjacent.append(
                {
                    "order_index": index,
                    "source_track_id": source,
                    "target_track_id": target,
                    "status": "present" if snapshots else "missing",
                    "snapshots": [dict(snapshot) for snapshot in snapshots],
                }
            )

        lineage = self._lineage(revision)
        document = {
            "schema": _DOCUMENT_SCHEMA,
            "revision": {
                "revision_id": str(revision["revision_id"]),
                "playlist_id": str(revision["playlist_id"]),
                "parent_revision_id": revision["parent_revision_id"],
                "revision_index": int(revision["revision_index"]),
                "source_proposal_id": str(revision["source_proposal_id"]),
                "source_path_id": str(revision["source_path_id"]),
                "operation": str(revision["operation"]),
                "content_fingerprint": str(revision["content_fingerprint"]),
                "created_at": str(revision["created_at"]),
            },
            "lineage": lineage,
            "tracks": tracks,
            "adjacent_transitions": adjacent,
            "m3u8_verification": verification,
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
        }
        return document, verification

    def _lineage(self, revision: dict[str, object]) -> list[dict[str, object]]:
        current = revision
        reversed_lineage: list[dict[str, object]] = []
        seen: set[str] = set()
        for _ in range(100):
            revision_id = str(current["revision_id"])
            if revision_id in seen:
                raise DesktopPlaylistEvidenceExportError(
                    "playlist_evidence_revision_invalid",
                    "The playlist revision lineage contains a cycle.",
                )
            seen.add(revision_id)
            reversed_lineage.append(
                {
                    "revision_id": revision_id,
                    "parent_revision_id": current["parent_revision_id"],
                    "revision_index": int(current["revision_index"]),
                    "operation": str(current["operation"]),
                    "content_fingerprint": str(current["content_fingerprint"]),
                }
            )
            parent_id = current["parent_revision_id"]
            if parent_id is None:
                break
            parent = self.revisions.get_revision(str(parent_id))
            if parent is None or parent["playlist_id"] != revision["playlist_id"]:
                raise DesktopPlaylistEvidenceExportError(
                    "playlist_evidence_revision_invalid",
                    "The playlist revision lineage is incomplete.",
                )
            current = parent
        else:
            raise DesktopPlaylistEvidenceExportError(
                "playlist_evidence_revision_invalid",
                "The playlist revision lineage exceeds the bounded history limit.",
            )
        lineage = list(reversed(reversed_lineage))
        for index, entry in enumerate(lineage):
            if entry["revision_index"] != index:
                raise DesktopPlaylistEvidenceExportError(
                    "playlist_evidence_revision_invalid",
                    "The playlist revision lineage order is invalid.",
                )
        return lineage

    def _revision(self, revision_id: str) -> dict[str, object]:
        token = self._token(revision_id)
        revision = self.revisions.get_revision(token)
        if revision is None:
            raise DesktopPlaylistEvidenceExportError(
                "playlist_evidence_revision_not_found",
                "The requested immutable playlist revision was not found.",
            )
        if revision.get("personal_dj_model_training_authorized") is not False:
            raise DesktopPlaylistEvidenceExportError(
                "playlist_evidence_revision_invalid",
                "The revision training boundary is invalid.",
            )
        if revision.get("production_activation_authorized") is not False:
            raise DesktopPlaylistEvidenceExportError(
                "playlist_evidence_revision_invalid",
                "The revision activation boundary is invalid.",
            )
        return revision

    @staticmethod
    def _items(revision: dict[str, object]) -> tuple[dict[str, object], ...]:
        raw = revision.get("items")
        if not isinstance(raw, (tuple, list)) or not 3 <= len(raw) <= 8:
            raise DesktopPlaylistEvidenceExportError(
                "playlist_evidence_revision_invalid",
                "The revision sequence is invalid.",
            )
        result: list[dict[str, object]] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict) or set(item) != {
                "order_index",
                "track_id",
                "display_name",
                "locked",
            }:
                raise DesktopPlaylistEvidenceExportError(
                    "playlist_evidence_revision_invalid",
                    "The revision sequence is invalid.",
                )
            if item["order_index"] != index:
                raise DesktopPlaylistEvidenceExportError(
                    "playlist_evidence_revision_invalid",
                    "The revision order is invalid.",
                )
            result.append(item)
        return tuple(result)

    @staticmethod
    def _token(value: str) -> str:
        if not isinstance(value, str) or not value or value.strip() != value or len(value) > 256:
            raise DesktopPlaylistEvidenceExportError(
                "invalid_playlist_evidence_export_request",
                "The evidence export revision identity is invalid.",
            )
        if "/" in value or "\\" in value or any(ch.isspace() or ord(ch) < 32 for ch in value):
            raise DesktopPlaylistEvidenceExportError(
                "invalid_playlist_evidence_export_request",
                "The evidence export revision identity is invalid.",
            )
        return value

    @staticmethod
    def _suggested_filename(revision_id: str) -> str:
        safe = "".join(ch for ch in revision_id if ch.isascii() and (ch.isalnum() or ch in "_-"))
        if not safe:
            safe = "playlist-revision"
        return f"APPLAYLIST_{safe[:96]}_evidence.json"


__all__ = [
    "DesktopPlaylistEvidenceExportError",
    "DesktopPlaylistEvidenceExportTransport",
]
