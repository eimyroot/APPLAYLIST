# Bundle 70 — Fresh Personal Holdout Runner R1

## Goal

Provide the local execution layer that turns the canonical Human Review Protocol R2 / Curation Calibration R3 contracts into a reproducible fresh personal holdout run.

The runner must stop before human labels are collected unless all pre-label evidence is frozen and auditable.

## Required execution order

1. Verify the local checkout is on canonical branch `feature/bundle-0-bootstrap`, its HEAD exactly matches the supplied canonical SHA, and the working tree is clean.
2. Validate private local-library snapshot R1.
3. Deterministically generate a bounded candidate case pool without reading human labels or challenger scores.
4. Materialize real-library optimizer evidence and blind A/B assignments locally, isolating per-case technical failures so one invalid candidate cannot abort the full pool.
5. Build engineering-only `HoldoutCandidate` rows.
6. Freeze `HoldoutCaseSamplingPolicy` and select at least 24 personal holdout cases with four cases per set role plus a frozen fallback reservoir.
7. Freeze replacement policy and effective cohort.
8. Compute Bundle 67 competitive-curation shadow comparisons for the selected cases and frozen fallback reservoir before reviewer workspace publication.
9. Persist a private pre-registration manifest containing selection, assignments, challenger evidence, fingerprints, and authority=false.
10. Finalize a reviewer-safe workspace bound to the exact preregistration/selection/cohort fingerprints.
11. Before reviewer publication, compare every effective A/B sequence against a required prior-exposure reviewer-packet registry. Reject any case that reproduces a previously exposed individual plan sequence or A/B pair.
12. Publish a reviewer-safe packet containing only anonymous Plan A / Plan B track sequences and the four R2 curation dimensions.
13. Create the review CSV with system binding metadata but leave all human judgments and clean-attestation assertions empty; no ratings, preferences, confidence, timestamps, or exposure claims may be fabricated.

## Critical isolation

`HOLDOUT_SELECTION_INPUTS` may include only frozen policy plus engineering/technical candidate metadata.

`HOLDOUT_SELECTION_INPUTS` must not include:
- human preference;
- human ratings;
- reviewer notes;
- competitive challenger scores;
- competitive challenger preference.

The challenger comparison is computed only after holdout selection is frozen, but before reviewer workspace publication. Challenger evidence is also frozen for the fallback reservoir so a later technical replacement cannot trigger post-label challenger computation.

## Freshness / prior-exposure rule

A new `case_id` alone is not evidence that a case is fresh. The formal run requires one or more prior blinded reviewer packets representing sequences already exposed to the reviewer.

Before Case 1 may be opened, the workspace finalizer must fail closed if an effective holdout case contains:
- an exact Plan A or Plan B sequence previously exposed to the reviewer; or
- an exact previously exposed A/B sequence pair, regardless of case identifier.

This prevents renamed or regenerated historical cases from being counted as independent personal-holdout evidence.

## Reviewer-safe dimensions

- energy_flow
- dramaturgical_fit
- set_coherence
- alternative_usefulness

Allowed preference values:
- plan_a
- plan_b
- tie
- abstain

No transition execution is requested in this runner.

The review CSV contains explicit R2 attestation fields, but the human-controlled fields remain empty at workspace freeze and must be completed only from the actual review session.

## Privacy

- local audio paths stay in private evidence only;
- no audio upload;
- no cloud MIR execution;
- reviewer packet must not expose absolute paths, optimizer strategy identity, shadow scores, or challenger preference;
- prior-exposure packets are used only for sequence-fingerprint exclusion and do not authorize publication of private evidence.

## Authority

- optimizer ranking activation: NO
- PDM training: NO
- release: NO
- deploy: NO
- production activation: NO
- merge: NO without separate `MERGE GO`
