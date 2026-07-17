from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from services.composition.shadow import CompositionShadowReport


RECEIPT_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class CompositionReceiptIssue:
    track_id: str
    code: str
    severity: str

    def to_dict(self) -> dict[str, str]:
        return {
            "track_id": self.track_id,
            "code": self.code,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class CompositionComparisonReceipt:
    schema_version: str
    run_id: str
    generated_at: str
    target_track_count: int
    bpm_min: float
    bpm_max: float
    mode: str
    legacy_track_ids: tuple[str, ...]
    canonical_track_ids: tuple[str, ...]
    canonical_status: str
    canonical_failure_reason: str | None
    candidate_count: int
    adapted_count: int
    rejected_count: int
    fallback_count: int
    overlap_count: int
    position_match_count: int
    legacy_coverage_ratio: float
    canonical_coverage_ratio: float
    adaptation_issues: tuple[CompositionReceiptIssue, ...]
    canonical_warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "request": {
                "target_track_count": self.target_track_count,
                "bpm_min": self.bpm_min,
                "bpm_max": self.bpm_max,
                "mode": self.mode,
            },
            "legacy": {
                "track_ids": list(self.legacy_track_ids),
            },
            "canonical": {
                "track_ids": list(self.canonical_track_ids),
                "status": self.canonical_status,
                "failure_reason": self.canonical_failure_reason,
                "warnings": list(self.canonical_warnings),
            },
            "quality": {
                "candidate_count": self.candidate_count,
                "adapted_count": self.adapted_count,
                "rejected_count": self.rejected_count,
                "fallback_count": self.fallback_count,
                "adaptation_issues": [
                    issue.to_dict() for issue in self.adaptation_issues
                ],
            },
            "comparison": {
                "overlap_count": self.overlap_count,
                "position_match_count": self.position_match_count,
                "legacy_coverage_ratio": self.legacy_coverage_ratio,
                "canonical_coverage_ratio": self.canonical_coverage_ratio,
            },
        }


def build_composition_comparison_receipt(
    *,
    run_id: str,
    generated_at: datetime,
    target_track_count: int,
    bpm_min: float,
    bpm_max: float,
    mode: str,
    report: CompositionShadowReport,
) -> CompositionComparisonReceipt:
    normalized_run_id = run_id.strip()
    if not normalized_run_id:
        raise ValueError("run_id must be a non-empty string")
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")

    normalized_time = generated_at.astimezone(timezone.utc)
    generated_at_text = normalized_time.isoformat().replace("+00:00", "Z")

    return CompositionComparisonReceipt(
        schema_version=RECEIPT_SCHEMA_VERSION,
        run_id=normalized_run_id,
        generated_at=generated_at_text,
        target_track_count=target_track_count,
        bpm_min=bpm_min,
        bpm_max=bpm_max,
        mode=mode,
        legacy_track_ids=report.legacy_track_ids,
        canonical_track_ids=report.canonical_track_ids,
        canonical_status=report.canonical_status.value,
        canonical_failure_reason=(
            report.canonical_failure_reason.value
            if report.canonical_failure_reason is not None
            else None
        ),
        candidate_count=report.candidate_count,
        adapted_count=report.adapted_count,
        rejected_count=report.rejected_count,
        fallback_count=report.fallback_count,
        overlap_count=report.overlap_count,
        position_match_count=report.position_match_count,
        legacy_coverage_ratio=report.legacy_coverage_ratio,
        canonical_coverage_ratio=report.canonical_coverage_ratio,
        adaptation_issues=tuple(
            CompositionReceiptIssue(
                track_id=issue.track_id,
                code=issue.code.value,
                severity=issue.severity.value,
            )
            for issue in report.adaptation_issues
        ),
        canonical_warnings=report.canonical_warnings,
    )
