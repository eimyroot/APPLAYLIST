from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from core.intelligence.music_dna import CalibrationState, Confidence
from core.intelligence.set_contract import SequenceState, SetStep
from core.intelligence.transition_contract import (
    ContextualTransitionProjection,
    EnergyDirection,
    TransitionAssessment,
    TransitionCompatibility,
    TransitionCost,
    TransitionEnergyEffect,
    TransitionExplanation,
    TransitionIdentity,
    TransitionRisk,
    TransitionStrategy,
    TransitionStrategyCandidate,
    TransitionWindow,
)
from data.connection import get_sqlite_connection


class MusicIntelligenceRepository:
    """Append-only SQLite persistence for transition snapshots and sequence states.

    A transition relation has a stable ``transition_id`` but its runtime v1 object also
    carries a context-bound projection and context-filtered strategy candidates. The
    repository therefore persists immutable *assessment snapshots* keyed by transition
    identity plus context identity/version. This prevents one context projection from
    overwriting another while preserving adjacency by the underlying transition ID.
    """

    def ensure_schema(self) -> None:
        with get_sqlite_connection() as conn:
            conn.executescript(
                '''
                CREATE TABLE IF NOT EXISTS transition_assessment_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    transition_id TEXT NOT NULL,
                    source_track_id TEXT NOT NULL,
                    source_segment_id TEXT NOT NULL,
                    target_track_id TEXT NOT NULL,
                    target_segment_id TEXT NOT NULL,
                    assessment_version TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    context_id TEXT NOT NULL,
                    context_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (transition_id, context_id, context_version)
                );

                CREATE INDEX IF NOT EXISTS idx_transition_snapshot_source
                    ON transition_assessment_snapshots(
                        source_track_id,
                        source_segment_id,
                        context_id,
                        context_version,
                        transition_id
                    );
                CREATE INDEX IF NOT EXISTS idx_transition_snapshot_target
                    ON transition_assessment_snapshots(
                        target_track_id,
                        target_segment_id,
                        context_id,
                        context_version,
                        transition_id
                    );

                CREATE TABLE IF NOT EXISTS sequence_state_revisions (
                    state_id TEXT NOT NULL,
                    state_version TEXT NOT NULL,
                    current_track_id TEXT,
                    current_segment_id TEXT,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (state_id, state_version)
                );

                CREATE INDEX IF NOT EXISTS idx_sequence_state_current
                    ON sequence_state_revisions(
                        current_track_id,
                        current_segment_id,
                        state_id,
                        state_version
                    );
                '''
            )
            conn.commit()

    def append_transition_assessment(self, assessment: TransitionAssessment) -> str:
        payload = self._canonical_payload(assessment)
        digest = self._digest(payload)
        projection = assessment.contextual_projection
        snapshot_id = self._snapshot_id(
            assessment.identity.transition_id,
            projection.context_id,
            projection.context_version,
        )
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                '''
                SELECT payload_json, payload_sha256
                FROM transition_assessment_snapshots
                WHERE snapshot_id = ?
                ''',
                (snapshot_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["payload_sha256"]) != digest or str(existing["payload_json"]) != payload:
                    raise ValueError("immutable transition assessment snapshot collision")
                conn.commit()
                return snapshot_id

            identity_collision = conn.execute(
                '''
                SELECT snapshot_id, payload_json, payload_sha256
                FROM transition_assessment_snapshots
                WHERE transition_id = ? AND context_id = ? AND context_version = ?
                ''',
                (
                    assessment.identity.transition_id,
                    projection.context_id,
                    projection.context_version,
                ),
            ).fetchone()
            if identity_collision is not None:
                if (
                    str(identity_collision["payload_sha256"]) != digest
                    or str(identity_collision["payload_json"]) != payload
                ):
                    raise ValueError("immutable transition context identity collision")
                conn.commit()
                return str(identity_collision["snapshot_id"])

            identity = assessment.identity
            conn.execute(
                '''
                INSERT INTO transition_assessment_snapshots (
                    snapshot_id,
                    transition_id,
                    source_track_id,
                    source_segment_id,
                    target_track_id,
                    target_segment_id,
                    assessment_version,
                    policy_version,
                    context_id,
                    context_version,
                    payload_json,
                    payload_sha256
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    snapshot_id,
                    identity.transition_id,
                    identity.source_track_id,
                    identity.source_segment_id,
                    identity.target_track_id,
                    identity.target_segment_id,
                    identity.assessment_version,
                    identity.policy_version,
                    projection.context_id,
                    projection.context_version,
                    payload,
                    digest,
                ),
            )
            conn.commit()
        return snapshot_id

    def get_transition_snapshot(self, snapshot_id: str) -> TransitionAssessment | None:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            row = conn.execute(
                '''
                SELECT payload_json, payload_sha256
                FROM transition_assessment_snapshots
                WHERE snapshot_id = ?
                ''',
                (snapshot_id,),
            ).fetchone()
        if row is None:
            return None
        payload = str(row["payload_json"])
        self._verify_payload(payload, str(row["payload_sha256"]))
        return self._decode_transition(json.loads(payload))

    def list_outgoing(
        self,
        *,
        source_track_id: str,
        source_segment_id: str,
        context_id: str | None = None,
        context_version: str | None = None,
        assessment_version: str | None = None,
        policy_version: str | None = None,
    ) -> tuple[TransitionAssessment, ...]:
        if (context_id is None) != (context_version is None):
            raise ValueError("context_id and context_version must be supplied together")
        clauses = ["source_track_id = ?", "source_segment_id = ?"]
        params: list[str] = [source_track_id, source_segment_id]
        for column, value in (
            ("context_id", context_id),
            ("context_version", context_version),
            ("assessment_version", assessment_version),
            ("policy_version", policy_version),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            rows = conn.execute(
                f'''
                SELECT payload_json, payload_sha256
                FROM transition_assessment_snapshots
                WHERE {' AND '.join(clauses)}
                ORDER BY transition_id, context_id, context_version, snapshot_id
                ''',
                tuple(params),
            ).fetchall()
        assessments: list[TransitionAssessment] = []
        for row in rows:
            payload = str(row["payload_json"])
            self._verify_payload(payload, str(row["payload_sha256"]))
            assessments.append(self._decode_transition(json.loads(payload)))
        return tuple(assessments)

    def append_sequence_state(self, state: SequenceState) -> None:
        payload = self._canonical_payload(state)
        digest = self._digest(payload)
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                '''
                SELECT payload_json, payload_sha256
                FROM sequence_state_revisions
                WHERE state_id = ? AND state_version = ?
                ''',
                (state.state_id, state.state_version),
            ).fetchone()
            if existing is not None:
                if str(existing["payload_sha256"]) != digest or str(existing["payload_json"]) != payload:
                    raise ValueError("immutable sequence state identity collision")
                conn.commit()
                return
            conn.execute(
                '''
                INSERT INTO sequence_state_revisions (
                    state_id,
                    state_version,
                    current_track_id,
                    current_segment_id,
                    payload_json,
                    payload_sha256
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    state.state_id,
                    state.state_version,
                    state.current_track_id,
                    state.current_segment_id,
                    payload,
                    digest,
                ),
            )
            conn.commit()

    def get_sequence_state(self, state_id: str, state_version: str) -> SequenceState | None:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            row = conn.execute(
                '''
                SELECT payload_json, payload_sha256
                FROM sequence_state_revisions
                WHERE state_id = ? AND state_version = ?
                ''',
                (state_id, state_version),
            ).fetchone()
        if row is None:
            return None
        payload = str(row["payload_json"])
        self._verify_payload(payload, str(row["payload_sha256"]))
        return self._decode_sequence_state(json.loads(payload))

    @staticmethod
    def _canonical_payload(value: object) -> str:
        return json.dumps(asdict(value), sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _digest(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def _verify_payload(cls, payload: str, expected_digest: str) -> None:
        if cls._digest(payload) != expected_digest:
            raise RuntimeError("stored Music Intelligence payload failed integrity verification")

    @staticmethod
    def _snapshot_id(transition_id: str, context_id: str, context_version: str) -> str:
        material = "|".join((transition_id, context_id, context_version))
        return "tas_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:40]

    @staticmethod
    def _confidence(raw: dict[str, Any]) -> Confidence:
        return Confidence(
            score=raw.get("score"),
            calibration_state=CalibrationState(str(raw["calibration_state"])),
            evidence_count=int(raw["evidence_count"]),
            disagreement=raw.get("disagreement"),
        )

    @classmethod
    def _decode_transition(cls, raw: dict[str, Any]) -> TransitionAssessment:
        identity_raw = raw["identity"]
        compatibility_raw = raw["compatibility_vector"]
        risk_raw = raw["risk_vector"]
        cost_raw = raw["cost_vector"]
        energy_raw = raw["energy_effect"]
        window_raw = raw["usable_window"]
        projection_raw = raw["contextual_projection"]

        identity = TransitionIdentity(
            transition_id=str(identity_raw["transition_id"]),
            source_track_id=str(identity_raw["source_track_id"]),
            source_segment_id=str(identity_raw["source_segment_id"]),
            target_track_id=str(identity_raw["target_track_id"]),
            target_segment_id=str(identity_raw["target_segment_id"]),
            assessment_version=str(identity_raw["assessment_version"]),
            policy_version=str(identity_raw["policy_version"]),
            music_dna_revision_refs=tuple(identity_raw["music_dna_revision_refs"]),  # type: ignore[arg-type]
            created_at=str(identity_raw["created_at"]),
        )
        compatibility = TransitionCompatibility(**compatibility_raw)
        risk = TransitionRisk(**risk_raw)
        cost = TransitionCost(**cost_raw)
        energy = TransitionEnergyEffect(
            source_energy_state=energy_raw.get("source_energy_state"),
            target_energy_state=energy_raw.get("target_energy_state"),
            delta=energy_raw.get("delta"),
            local_curve_alignment=energy_raw.get("local_curve_alignment"),
            direction=EnergyDirection(str(energy_raw["direction"])),
            confidence=cls._confidence(energy_raw["confidence"]),
        )
        strategies = tuple(
            TransitionStrategyCandidate(
                strategy=TransitionStrategy(str(item["strategy"])),
                suitability=float(item["suitability"]),
                required_capabilities=tuple(item["required_capabilities"]),
                explanation_codes=tuple(item["explanation_codes"]),
            )
            for item in raw["candidate_strategies"]
        )
        window = TransitionWindow(
            source_start_seconds=window_raw["source_start_seconds"],
            source_end_seconds=window_raw["source_end_seconds"],
            target_start_seconds=window_raw["target_start_seconds"],
            target_end_seconds=window_raw["target_end_seconds"],
            source_bar_count=window_raw.get("source_bar_count"),
            target_bar_count=window_raw.get("target_bar_count"),
            confidence=cls._confidence(window_raw["confidence"]),
        )
        projection = ContextualTransitionProjection(
            context_id=str(projection_raw["context_id"]),
            context_version=str(projection_raw["context_version"]),
            score=projection_raw.get("score"),
            blocked_reasons=tuple(projection_raw["blocked_reasons"]),
            rank_features=tuple(projection_raw["rank_features"]),
            confidence=cls._confidence(projection_raw["confidence"]),
            explanation_codes=tuple(projection_raw["explanation_codes"]),
        )
        explanations = tuple(
            TransitionExplanation(
                code=str(item["code"]),
                severity=str(item["severity"]),
                dimension=str(item["dimension"]),
                evidence_refs=tuple(item["evidence_refs"]),
                confidence=cls._confidence(item["confidence"]),
            )
            for item in raw["explanations"]
        )
        preferred_raw = raw.get("preferred_strategy")
        return TransitionAssessment(
            identity=identity,
            compatibility_vector=compatibility,
            risk_vector=risk,
            cost_vector=cost,
            energy_effect=energy,
            candidate_strategies=strategies,
            preferred_strategy=(
                TransitionStrategy(str(preferred_raw)) if preferred_raw is not None else None
            ),
            usable_window=window,
            contextual_projection=projection,
            confidence=cls._confidence(raw["confidence"]),
            explanations=explanations,
            evidence_refs=tuple(raw["evidence_refs"]),
            warnings=tuple(raw.get("warnings", ())),
        )

    @staticmethod
    def _decode_sequence_state(raw: dict[str, Any]) -> SequenceState:
        steps = tuple(
            SetStep(
                order_index=int(item["order_index"]),
                track_id=str(item["track_id"]),
                segment_id=str(item["segment_id"]),
                phase_id=str(item["phase_id"]),
                incoming_transition_id=item.get("incoming_transition_id"),
                chosen_strategy=(
                    TransitionStrategy(str(item["chosen_strategy"]))
                    if item.get("chosen_strategy") is not None
                    else None
                ),
                local_projection_score=item.get("local_projection_score"),
                explanation_codes=tuple(item.get("explanation_codes", ())),
                evidence_refs=tuple(item.get("evidence_refs", ())),
            )
            for item in raw["selected_steps"]
        )
        return SequenceState(
            state_id=str(raw["state_id"]),
            state_version=str(raw["state_version"]),
            selected_steps=steps,
            current_track_id=raw.get("current_track_id"),
            current_segment_id=raw.get("current_segment_id"),
            used_track_ids=tuple(raw["used_track_ids"]),
            cumulative_duration_seconds=float(raw["cumulative_duration_seconds"]),
            current_energy_state=raw.get("current_energy_state"),
            satisfied_required_track_ids=tuple(raw.get("satisfied_required_track_ids", ())),
            remaining_required_track_ids=tuple(raw.get("remaining_required_track_ids", ())),
            warnings=tuple(raw.get("warnings", ())),
            evidence_refs=tuple(raw.get("evidence_refs", ())),
        )


__all__ = ["MusicIntelligenceRepository"]
