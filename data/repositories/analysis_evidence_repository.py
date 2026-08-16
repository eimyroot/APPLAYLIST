from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from uuid import uuid4

from data.connection import get_sqlite_connection
from data.models.analysis_evidence_record import (
    AnalysisCorrectionRecord,
    AnalysisEvidenceRecord,
)


class AnalysisEvidenceRepository:
    def ensure_schema(self) -> None:
        with get_sqlite_connection() as conn:
            conn.executescript(
                '''
                CREATE TABLE IF NOT EXISTS analysis_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    track_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    analysis_version TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'succeeded'
                        CHECK (status IN ('succeeded', 'failed')),
                    provider_version TEXT,
                    algorithm_version TEXT,
                    bpm REAL,
                    bpm_confidence REAL,
                    key_tonic TEXT,
                    key_scale TEXT,
                    camelot TEXT,
                    key_confidence REAL,
                    energy REAL,
                    loudness_db REAL,
                    duration_seconds REAL,
                    beat_stability REAL,
                    harmonic_ratio REAL,
                    percussive_ratio REAL,
                    genre_hint TEXT,
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    error_code TEXT,
                    error_detail TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_analysis_evidence_track_created
                    ON analysis_evidence(track_id, created_at, evidence_id);
                CREATE INDEX IF NOT EXISTS idx_analysis_evidence_status_created
                    ON analysis_evidence(status, created_at, evidence_id);

                CREATE TABLE IF NOT EXISTS analysis_corrections (
                    correction_id TEXT PRIMARY KEY,
                    track_id TEXT NOT NULL,
                    base_evidence_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_analysis_corrections_track_created
                    ON analysis_corrections(track_id, created_at, correction_id);
                CREATE INDEX IF NOT EXISTS idx_analysis_corrections_base_created
                    ON analysis_corrections(base_evidence_id, created_at, correction_id);
                '''
            )
            self._ensure_columns(conn)
            conn.commit()

    def append_evidence(
        self,
        *,
        track_id: str,
        provider: str,
        analysis_version: str,
        status: str = "succeeded",
        provider_version: str | None = None,
        algorithm_version: str | None = None,
        bpm: float | None = None,
        bpm_confidence: float | None = None,
        key_tonic: str | None = None,
        key_scale: str | None = None,
        camelot: str | None = None,
        key_confidence: float | None = None,
        energy: float | None = None,
        loudness_db: float | None = None,
        duration_seconds: float | None = None,
        beat_stability: float | None = None,
        harmonic_ratio: float | None = None,
        percussive_ratio: float | None = None,
        genre_hint: str | None = None,
        warnings: tuple[str, ...] = (),
        error_code: str | None = None,
        error_detail: str | None = None,
        evidence_id: str | None = None,
    ) -> AnalysisEvidenceRecord:
        normalized_track_id = self._required_text(track_id, "track_id", 256)
        normalized_provider = self._required_text(provider, "provider", 128).lower()
        normalized_analysis_version = self._required_text(
            analysis_version,
            "analysis_version",
            128,
        )
        normalized_status = self._normalize_status(status)
        normalized_warnings = self._normalize_warnings(warnings)
        normalized_error_code = self._optional_text(error_code, 128)
        normalized_error_detail = self._optional_text(error_detail, 512)
        if normalized_status == "succeeded" and (
            normalized_error_code is not None or normalized_error_detail is not None
        ):
            raise ValueError("successful analysis evidence cannot contain failure details")
        if normalized_status == "failed" and normalized_error_code is None:
            raise ValueError("failed analysis evidence requires an error_code")

        record = AnalysisEvidenceRecord(
            evidence_id=evidence_id or f"ae_{uuid4().hex}",
            track_id=normalized_track_id,
            provider=normalized_provider,
            analysis_version=normalized_analysis_version,
            status=normalized_status,
            provider_version=self._optional_text(provider_version, 128),
            algorithm_version=self._optional_text(algorithm_version, 128),
            bpm=self._optional_number(bpm, "bpm", minimum=20.0, maximum=400.0),
            bpm_confidence=self._optional_number(
                bpm_confidence,
                "bpm_confidence",
                minimum=0.0,
                maximum=1.0,
            ),
            key_tonic=self._optional_text(key_tonic, 16),
            key_scale=self._optional_scale(key_scale),
            camelot=self._optional_camelot(camelot),
            key_confidence=self._optional_number(
                key_confidence,
                "key_confidence",
                minimum=0.0,
                maximum=1.0,
            ),
            energy=self._optional_number(energy, "energy", minimum=0.0, maximum=1.0),
            loudness_db=self._optional_number(
                loudness_db,
                "loudness_db",
                minimum=None,
                maximum=None,
            ),
            duration_seconds=self._optional_number(
                duration_seconds,
                "duration_seconds",
                minimum=0.0,
                maximum=None,
            ),
            beat_stability=self._optional_number(
                beat_stability,
                "beat_stability",
                minimum=0.0,
                maximum=1.0,
            ),
            harmonic_ratio=self._optional_number(
                harmonic_ratio,
                "harmonic_ratio",
                minimum=0.0,
                maximum=1.0,
            ),
            percussive_ratio=self._optional_number(
                percussive_ratio,
                "percussive_ratio",
                minimum=0.0,
                maximum=1.0,
            ),
            genre_hint=self._optional_text(genre_hint, 128),
            warnings=normalized_warnings,
            error_code=normalized_error_code,
            error_detail=normalized_error_detail,
        )
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            conn.execute(
                '''
                INSERT INTO analysis_evidence (
                    evidence_id, track_id, provider, analysis_version, status,
                    provider_version, algorithm_version, bpm, bpm_confidence,
                    key_tonic, key_scale, camelot, key_confidence, energy,
                    loudness_db, duration_seconds, beat_stability, harmonic_ratio,
                    percussive_ratio, genre_hint, warnings_json, error_code, error_detail
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    record.evidence_id,
                    record.track_id,
                    record.provider,
                    record.analysis_version,
                    record.status,
                    record.provider_version,
                    record.algorithm_version,
                    record.bpm,
                    record.bpm_confidence,
                    record.key_tonic,
                    record.key_scale,
                    record.camelot,
                    record.key_confidence,
                    record.energy,
                    record.loudness_db,
                    record.duration_seconds,
                    record.beat_stability,
                    record.harmonic_ratio,
                    record.percussive_ratio,
                    record.genre_hint,
                    json.dumps(record.warnings, separators=(",", ":")),
                    record.error_code,
                    record.error_detail,
                ),
            )
            conn.commit()
        inserted = self.get_evidence(record.evidence_id)
        if inserted is None:
            raise RuntimeError("analysis evidence insert was not observable")
        return inserted

    def append_correction(
        self,
        *,
        track_id: str,
        base_evidence_id: str,
        values: Mapping[str, object],
        reason: str | None = None,
        correction_id: str | None = None,
    ) -> AnalysisCorrectionRecord:
        normalized_track_id = self._required_text(track_id, "track_id", 256)
        normalized_base_evidence_id = self._required_text(
            base_evidence_id,
            "base_evidence_id",
            256,
        )
        base = self.get_evidence(normalized_base_evidence_id)
        if base is None or base.track_id != normalized_track_id or base.status != "succeeded":
            raise ValueError("correction must reference successful evidence for the same track")
        payload = self._normalize_correction_values(values)
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        record = AnalysisCorrectionRecord(
            correction_id=correction_id or f"ac_{uuid4().hex}",
            track_id=normalized_track_id,
            base_evidence_id=normalized_base_evidence_id,
            payload_json=payload_json,
            reason=self._optional_text(reason, 512),
        )
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            conn.execute(
                '''
                INSERT INTO analysis_corrections (
                    correction_id, track_id, base_evidence_id, payload_json, reason
                )
                VALUES (?, ?, ?, ?, ?)
                ''',
                (
                    record.correction_id,
                    record.track_id,
                    record.base_evidence_id,
                    record.payload_json,
                    record.reason,
                ),
            )
            conn.commit()
        inserted = self.get_correction(record.correction_id)
        if inserted is None:
            raise RuntimeError("analysis correction insert was not observable")
        return inserted

    def get_evidence(self, evidence_id: str) -> AnalysisEvidenceRecord | None:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            row = conn.execute(
                "SELECT * FROM analysis_evidence WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
        if row is None:
            return None
        return self._evidence_from_row(dict(row))

    def get_correction(self, correction_id: str) -> AnalysisCorrectionRecord | None:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            row = conn.execute(
                "SELECT * FROM analysis_corrections WHERE correction_id = ?",
                (correction_id,),
            ).fetchone()
        if row is None:
            return None
        return AnalysisCorrectionRecord(**dict(row))

    def latest_evidence_for_track(self, track_id: str) -> AnalysisEvidenceRecord | None:
        return self._latest_evidence(track_id, succeeded_only=False)

    def latest_success_for_track(self, track_id: str) -> AnalysisEvidenceRecord | None:
        return self._latest_evidence(track_id, succeeded_only=True)

    def list_latest_attempts(self) -> list[AnalysisEvidenceRecord]:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            rows = conn.execute(
                '''
                SELECT evidence.*
                FROM analysis_evidence AS evidence
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM analysis_evidence AS newer
                    WHERE newer.track_id = evidence.track_id
                      AND (
                          newer.created_at > evidence.created_at
                          OR (
                              newer.created_at = evidence.created_at
                              AND newer.evidence_id > evidence.evidence_id
                          )
                      )
                )
                ORDER BY evidence.track_id
                '''
            ).fetchall()
        return [self._evidence_from_row(dict(row)) for row in rows]

    def latest_correction_for_track(self, track_id: str) -> AnalysisCorrectionRecord | None:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            row = conn.execute(
                '''
                SELECT * FROM analysis_corrections
                WHERE track_id = ?
                ORDER BY created_at DESC, correction_id DESC
                LIMIT 1
                ''',
                (track_id,),
            ).fetchone()
        if row is None:
            return None
        return AnalysisCorrectionRecord(**dict(row))

    def latest_active_correction(
        self,
        track_id: str,
        base_evidence_id: str,
    ) -> AnalysisCorrectionRecord | None:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            row = conn.execute(
                '''
                SELECT * FROM analysis_corrections
                WHERE track_id = ? AND base_evidence_id = ?
                ORDER BY created_at DESC, correction_id DESC
                LIMIT 1
                ''',
                (track_id, base_evidence_id),
            ).fetchone()
        if row is None:
            return None
        return AnalysisCorrectionRecord(**dict(row))

    def _latest_evidence(
        self,
        track_id: str,
        *,
        succeeded_only: bool,
    ) -> AnalysisEvidenceRecord | None:
        self.ensure_schema()
        status_clause = "AND status = 'succeeded'" if succeeded_only else ""
        with get_sqlite_connection() as conn:
            row = conn.execute(
                f'''
                SELECT * FROM analysis_evidence
                WHERE track_id = ? {status_clause}
                ORDER BY created_at DESC, evidence_id DESC
                LIMIT 1
                ''',
                (track_id,),
            ).fetchone()
        if row is None:
            return None
        return self._evidence_from_row(dict(row))

    @staticmethod
    def _ensure_columns(conn: object) -> None:
        evidence_columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(analysis_evidence)").fetchall()  # type: ignore[attr-defined]
        }
        for name, declaration in (
            ("status", "TEXT NOT NULL DEFAULT 'succeeded'"),
            ("loudness_db", "REAL"),
            ("beat_stability", "REAL"),
            ("harmonic_ratio", "REAL"),
            ("percussive_ratio", "REAL"),
            ("genre_hint", "TEXT"),
            ("error_code", "TEXT"),
            ("error_detail", "TEXT"),
        ):
            if name not in evidence_columns:
                conn.execute(  # type: ignore[attr-defined]
                    f"ALTER TABLE analysis_evidence ADD COLUMN {name} {declaration}"
                )

        correction_columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(analysis_corrections)").fetchall()  # type: ignore[attr-defined]
        }
        if "base_evidence_id" not in correction_columns:
            conn.execute(  # type: ignore[attr-defined]
                "ALTER TABLE analysis_corrections "
                "ADD COLUMN base_evidence_id TEXT NOT NULL DEFAULT ''"
            )

    @staticmethod
    def _normalize_status(value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("analysis evidence status must be text")
        normalized = value.strip().lower()
        if normalized not in {"succeeded", "failed"}:
            raise ValueError("analysis evidence status must be succeeded or failed")
        return normalized

    @staticmethod
    def _required_text(value: str, field: str, maximum_length: int) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field} must be text")
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field} must be non-empty")
        if len(normalized) > maximum_length:
            raise ValueError(f"{field} is too long")
        return normalized

    @staticmethod
    def _optional_text(value: str | None, maximum_length: int) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError("optional text field must be text")
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > maximum_length:
            raise ValueError("optional text field is too long")
        return normalized

    @classmethod
    def _optional_scale(cls, value: str | None) -> str | None:
        normalized = cls._optional_text(value, 16)
        if normalized is None:
            return None
        normalized = normalized.lower()
        if normalized not in {"major", "minor"}:
            raise ValueError("key_scale must be major or minor")
        return normalized

    @classmethod
    def _optional_camelot(cls, value: str | None) -> str | None:
        normalized = cls._optional_text(value, 3)
        if normalized is None:
            return None
        normalized = normalized.upper()
        if re.fullmatch(r"(?:[1-9]|1[0-2])[AB]", normalized) is None:
            raise ValueError("camelot must be between 1A and 12B")
        return normalized

    @staticmethod
    def _optional_number(
        value: float | int | None,
        field: str,
        *,
        minimum: float | None,
        maximum: float | None,
    ) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field} must be numeric")
        normalized = float(value)
        if not math.isfinite(normalized):
            raise ValueError(f"{field} must be finite")
        if minimum is not None and normalized < minimum:
            raise ValueError(f"{field} is below minimum")
        if maximum is not None and normalized > maximum:
            raise ValueError(f"{field} is above maximum")
        return normalized

    @classmethod
    def _normalize_warnings(cls, warnings: tuple[str, ...]) -> tuple[str, ...]:
        if not isinstance(warnings, tuple):
            raise TypeError("warnings must be a tuple")
        if len(warnings) > 32:
            raise ValueError("too many analysis warnings")
        normalized: list[str] = []
        for warning in warnings:
            text = cls._required_text(warning, "warning", 256)
            if text not in normalized:
                normalized.append(text)
        return tuple(normalized)

    @classmethod
    def _normalize_correction_values(
        cls,
        values: Mapping[str, object],
    ) -> dict[str, object]:
        if not isinstance(values, Mapping):
            raise TypeError("correction values must be an object")
        allowed = {"bpm", "key_tonic", "key_scale", "camelot", "energy"}
        unknown = set(values) - allowed
        if unknown:
            raise ValueError("correction contains unsupported fields")
        if not values:
            raise ValueError("correction must change at least one field")
        payload: dict[str, object] = {}
        if "bpm" in values:
            payload["bpm"] = cls._optional_number(
                values["bpm"],  # type: ignore[arg-type]
                "bpm",
                minimum=20.0,
                maximum=400.0,
            )
        if "energy" in values:
            payload["energy"] = cls._optional_number(
                values["energy"],  # type: ignore[arg-type]
                "energy",
                minimum=0.0,
                maximum=1.0,
            )
        if "key_tonic" in values:
            raw_tonic = values["key_tonic"]
            if raw_tonic is not None and not isinstance(raw_tonic, str):
                raise TypeError("key_tonic must be text or null")
            payload["key_tonic"] = cls._optional_text(raw_tonic, 16)  # type: ignore[arg-type]
        if "key_scale" in values:
            raw_scale = values["key_scale"]
            if raw_scale is not None and not isinstance(raw_scale, str):
                raise TypeError("key_scale must be text or null")
            payload["key_scale"] = cls._optional_scale(raw_scale)  # type: ignore[arg-type]
        if "camelot" in values:
            raw_camelot = values["camelot"]
            if raw_camelot is not None and not isinstance(raw_camelot, str):
                raise TypeError("camelot must be text or null")
            payload["camelot"] = cls._optional_camelot(raw_camelot)  # type: ignore[arg-type]
        return payload

    @staticmethod
    def _evidence_from_row(row: dict[str, object]) -> AnalysisEvidenceRecord:
        warnings = json.loads(str(row["warnings_json"]))
        if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
            raise ValueError("stored analysis warnings are invalid")
        return AnalysisEvidenceRecord(
            evidence_id=str(row["evidence_id"]),
            track_id=str(row["track_id"]),
            provider=str(row["provider"]),
            analysis_version=str(row["analysis_version"]),
            status=str(row["status"]),
            provider_version=(
                str(row["provider_version"])
                if row["provider_version"] is not None
                else None
            ),
            algorithm_version=(
                str(row["algorithm_version"])
                if row["algorithm_version"] is not None
                else None
            ),
            bpm=float(row["bpm"]) if row["bpm"] is not None else None,
            bpm_confidence=(
                float(row["bpm_confidence"])
                if row["bpm_confidence"] is not None
                else None
            ),
            key_tonic=(str(row["key_tonic"]) if row["key_tonic"] is not None else None),
            key_scale=(str(row["key_scale"]) if row["key_scale"] is not None else None),
            camelot=(str(row["camelot"]) if row["camelot"] is not None else None),
            key_confidence=(
                float(row["key_confidence"])
                if row["key_confidence"] is not None
                else None
            ),
            energy=float(row["energy"]) if row["energy"] is not None else None,
            loudness_db=(
                float(row["loudness_db"])
                if row["loudness_db"] is not None
                else None
            ),
            duration_seconds=(
                float(row["duration_seconds"])
                if row["duration_seconds"] is not None
                else None
            ),
            beat_stability=(
                float(row["beat_stability"])
                if row["beat_stability"] is not None
                else None
            ),
            harmonic_ratio=(
                float(row["harmonic_ratio"])
                if row["harmonic_ratio"] is not None
                else None
            ),
            percussive_ratio=(
                float(row["percussive_ratio"])
                if row["percussive_ratio"] is not None
                else None
            ),
            genre_hint=(str(row["genre_hint"]) if row["genre_hint"] is not None else None),
            warnings=tuple(warnings),
            error_code=(str(row["error_code"]) if row["error_code"] is not None else None),
            error_detail=(
                str(row["error_detail"])
                if row["error_detail"] is not None
                else None
            ),
            created_at=(str(row["created_at"]) if row["created_at"] is not None else None),
        )
