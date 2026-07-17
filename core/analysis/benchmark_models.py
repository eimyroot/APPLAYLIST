from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from core.analysis.provider_contract import CanonicalAnalysisResult


MANIFEST_SCHEMA_VERSION = "applaylist-mir-benchmark-manifest-v1"
REPORT_SCHEMA_VERSION = "applaylist-mir-benchmark-report-v1"


class BenchmarkManifestError(ValueError):
    """Raised when benchmark input cannot be trusted."""


class AnalysisService(Protocol):
    def analyze_path(
        self,
        path: str,
        *,
        preferred_provider: str | None = None,
    ) -> CanonicalAnalysisResult: ...


@dataclass(frozen=True, slots=True)
class BenchmarkReference:
    bpm: float | None = None
    alternate_bpms: tuple[float, ...] = ()
    key_tonic: str | None = None
    key_scale: str | None = None
    camelot: str | None = None
    energy_rank: float | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkItem:
    item_id: str
    relative_path: str
    reference: BenchmarkReference


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    schema_version: str
    dataset_name: str
    dataset_version: str
    source: str
    license_id: str
    dataset_checksum: str
    dataset_root: str
    manifest_path: str
    manifest_sha256: str
    items: tuple[BenchmarkItem, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkResultRow:
    item_id: str
    relative_path: str
    status: str
    runtime_ms: float
    error_code: str | None
    error_message: str | None
    provider: str | None
    provider_version: str | None
    algorithm_version: str | None
    bpm_reference: float | None
    bpm_estimated: float | None
    bpm_classification: str | None
    bpm_error_percent: float | None
    key_reference: str | None
    key_estimated: str | None
    key_classification: str | None
    energy_reference_rank: float | None
    energy_estimated: float | None
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    schema_version: str
    generated_at: str
    source_commit: str
    preferred_provider: str | None
    manifest: dict[str, Any]
    environment: dict[str, Any]
    rows: tuple[BenchmarkResultRow, ...]
    summary: dict[str, Any]
    acceptance_gates: dict[str, bool | None]
    decision_status: str = "manual_review_required"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "source_commit": self.source_commit,
            "preferred_provider": self.preferred_provider,
            "manifest": self.manifest,
            "environment": self.environment,
            "rows": [asdict(row) for row in self.rows],
            "summary": self.summary,
            "acceptance_gates": self.acceptance_gates,
            "decision_status": self.decision_status,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
