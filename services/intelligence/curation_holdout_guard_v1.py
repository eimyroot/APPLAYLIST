from __future__ import annotations

import hashlib
from collections.abc import Sequence

from core.intelligence.curated_real_library_review_contract import CuratedReviewCase
from core.intelligence.curation_holdout_guard_contract import (
    HOLDOUT_GUARD_VERSION,
    CurationAssignmentBatchManifest,
    DevelopmentEvidenceExclusionRegistry,
    HoldoutSelectionBasis,
)
from core.intelligence.curation_review_v2_contract import (
    CurationBlindAssignmentV2,
    HoldoutValidationManifest,
)


class CurationHoldoutGuardError(ValueError):
    """Fail-closed holdout lineage / assignment verification error."""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def assignment_seed_commitment(private_seed: str) -> str:
    normalized = str(private_seed).strip()
    if not normalized:
        raise CurationHoldoutGuardError("assignment private seed must not be empty")
    return _sha256_text(f"applaylist-assignment-seed-r1|{normalized}")


def _assignment_fingerprint(
    *,
    private_seed: str,
    reviewer_ref: str,
    case_id: str,
    slot_a_plan_id: str,
    slot_b_plan_id: str,
) -> str:
    material = "|".join(
        (
            "applaylist-curation-assignment-r1",
            private_seed,
            reviewer_ref,
            case_id,
            slot_a_plan_id,
            slot_b_plan_id,
        )
    )
    return _sha256_text(material)


def build_counterbalanced_assignment_batch(
    *,
    cases: Sequence[CuratedReviewCase],
    reviewer_refs: Sequence[str],
    private_seed: str,
    generated_at: str,
) -> tuple[tuple[CurationBlindAssignmentV2, ...], CurationAssignmentBatchManifest]:
    source_cases = tuple(cases)
    reviewers = tuple(sorted({str(item).strip() for item in reviewer_refs if str(item).strip()}))
    if not source_cases:
        raise CurationHoldoutGuardError("assignment batch requires source cases")
    if len({item.case_id for item in source_cases}) != len(source_cases):
        raise CurationHoldoutGuardError("assignment source case identities must be unique")
    if not reviewers:
        raise CurationHoldoutGuardError("assignment batch requires reviewer identities")
    normalized_seed = str(private_seed).strip()
    if not normalized_seed:
        raise CurationHoldoutGuardError("assignment private seed must not be empty")

    # Freeze one deterministic case order from the private seed. The alternating
    # placement plus reviewer-specific parity offset guarantees as-even-as-possible
    # A/B allocation for each reviewer and across the batch while keeping mappings
    # unpredictable without the private seed.
    ordered_cases = tuple(
        sorted(
            source_cases,
            key=lambda case: _sha256_text(
                f"applaylist-case-order-r1|{normalized_seed}|{case.case_id}"
            ),
        )
    )

    assignments: list[CurationBlindAssignmentV2] = []
    fingerprints: list[str] = []
    for reviewer_index, reviewer_ref in enumerate(reviewers):
        reviewer_offset = int(
            _sha256_text(
                f"applaylist-reviewer-offset-r1|{normalized_seed}|{reviewer_ref}"
            ),
            16,
        ) % 2
        # Alternate reviewer parity as a second counterbalance axis.
        reviewer_offset ^= reviewer_index % 2
        for case_index, case in enumerate(ordered_cases):
            greedy_in_a = (case_index + reviewer_offset) % 2 == 0
            slot_a = case.greedy_plan.plan_id if greedy_in_a else case.beam_plan.plan_id
            slot_b = case.beam_plan.plan_id if greedy_in_a else case.greedy_plan.plan_id
            fingerprint = _assignment_fingerprint(
                private_seed=normalized_seed,
                reviewer_ref=reviewer_ref,
                case_id=case.case_id,
                slot_a_plan_id=slot_a,
                slot_b_plan_id=slot_b,
            )
            assignment_id = f"curation-assignment:{fingerprint[:32]}"
            assignments.append(
                CurationBlindAssignmentV2(
                    assignment_id=assignment_id,
                    case_id=case.case_id,
                    reviewer_ref=reviewer_ref,
                    slot_a_plan_id=slot_a,
                    slot_b_plan_id=slot_b,
                    assignment_fingerprint=fingerprint,
                    algorithm_identity_hidden=True,
                )
            )
            fingerprints.append(fingerprint)

    commitment = assignment_seed_commitment(normalized_seed)
    manifest_material = "|".join(
        (
            commitment,
            *reviewers,
            *(case.case_id for case in ordered_cases),
            *sorted(fingerprints),
        )
    )
    manifest = CurationAssignmentBatchManifest(
        batch_id=f"curation-assignment-batch:{_sha256_text(manifest_material)}",
        batch_version=HOLDOUT_GUARD_VERSION,
        assignment_seed_commitment=commitment,
        reviewer_refs=reviewers,
        case_ids=tuple(case.case_id for case in ordered_cases),
        assignment_fingerprints=tuple(sorted(fingerprints)),
        generated_at=str(generated_at).strip(),
        algorithm_identity_hidden=True,
        activation_authorized=False,
        personal_dj_model_training_authorized=False,
    )
    return tuple(assignments), manifest


def validate_assignment_batch(
    *,
    cases: Sequence[CuratedReviewCase],
    assignments: Sequence[CurationBlindAssignmentV2],
    manifest: CurationAssignmentBatchManifest,
    private_seed: str,
) -> None:
    source_cases = tuple(cases)
    actual_assignments = tuple(assignments)
    expected_assignments, expected_manifest = build_counterbalanced_assignment_batch(
        cases=source_cases,
        reviewer_refs=manifest.reviewer_refs,
        private_seed=private_seed,
        generated_at=manifest.generated_at,
    )
    if manifest.assignment_seed_commitment != expected_manifest.assignment_seed_commitment:
        raise CurationHoldoutGuardError("assignment seed commitment mismatch")
    if manifest.case_ids != expected_manifest.case_ids:
        raise CurationHoldoutGuardError("assignment batch case identities mismatch")
    if manifest.assignment_fingerprints != expected_manifest.assignment_fingerprints:
        raise CurationHoldoutGuardError("assignment batch fingerprints mismatch")

    expected_by_key = {
        (item.reviewer_ref, item.case_id): item for item in expected_assignments
    }
    actual_by_key: dict[tuple[str, str], CurationBlindAssignmentV2] = {}
    for item in actual_assignments:
        key = (item.reviewer_ref, item.case_id)
        if key in actual_by_key:
            raise CurationHoldoutGuardError("duplicate reviewer/case assignment")
        actual_by_key[key] = item
    if set(actual_by_key) != set(expected_by_key):
        raise CurationHoldoutGuardError("assignment batch does not cover reviewer x case exactly")
    for key, expected in expected_by_key.items():
        actual = actual_by_key[key]
        if (
            actual.assignment_id != expected.assignment_id
            or actual.slot_a_plan_id != expected.slot_a_plan_id
            or actual.slot_b_plan_id != expected.slot_b_plan_id
            or actual.assignment_fingerprint != expected.assignment_fingerprint
        ):
            raise CurationHoldoutGuardError("reviewer-specific assignment derivation mismatch")


def validate_holdout_lineage(
    *,
    cases: Sequence[CuratedReviewCase],
    holdout_manifest: HoldoutValidationManifest,
    development_registry: DevelopmentEvidenceExclusionRegistry,
    selection_basis: HoldoutSelectionBasis,
) -> None:
    source_cases = tuple(cases)
    if selection_basis.selection_scope is not holdout_manifest.selection_scope:
        raise CurationHoldoutGuardError("holdout selection scope/basis mismatch")

    case_ids = {item.case_id for item in source_cases}
    scenario_fingerprints = {item.scenario_fingerprint for item in source_cases}
    development_case_ids = set(development_registry.case_ids)
    development_scenarios = set(development_registry.scenario_fingerprints)
    overlap_cases = case_ids & development_case_ids
    overlap_scenarios = scenario_fingerprints & development_scenarios
    if overlap_cases:
        raise CurationHoldoutGuardError(
            "holdout contains prior development case identity"
        )
    if overlap_scenarios:
        raise CurationHoldoutGuardError(
            "holdout contains prior development scenario fingerprint"
        )


__all__ = [
    "CurationHoldoutGuardError",
    "assignment_seed_commitment",
    "build_counterbalanced_assignment_batch",
    "validate_assignment_batch",
    "validate_holdout_lineage",
]
