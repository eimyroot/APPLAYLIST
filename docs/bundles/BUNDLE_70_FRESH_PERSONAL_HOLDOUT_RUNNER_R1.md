# Bundle 70 — Fresh Personal Holdout Runner R1

## Goal

Provide the local execution layer that turns the canonical Human Review Protocol R2 / Curation Calibration R3 contracts into a reproducible fresh personal holdout run.

The runner must stop before human labels are collected unless all pre-label evidence is frozen and auditable.

## Required execution order

1. Validate private local-library snapshot R1.
2. Deterministically generate a bounded candidate case pool without reading human labels or challenger scores.
3. Materialize real-library optimizer evidence and blind A/B assignments locally.
4. Build engineering-only `HoldoutCandidate` rows.
5. Freeze `HoldoutCaseSamplingPolicy` and select at least 24 personal holdout cases with four cases per set role plus a frozen fallback reservoir.
6. Freeze replacement policy and effective cohort.
7. Compute Bundle 67 competitive-curation shadow comparisons for the effective selected cases before reviewer workspace publication.
8. Persist a private pre-registration manifest containing selection, assignments, challenger evidence, fingerprints, and authority=false.
9. Publish a reviewer-safe packet containing only anonymous Plan A / Plan B track sequences and the four R2 curation dimensions.
10. Create an empty review CSV; no ratings, preferences, confidence, or timestamps may be fabricated.

## Critical isolation

`HOLDOUT_SELECTION_INPUTS` may include only frozen policy plus engineering/technical candidate metadata.

`HOLDOUT_SELECTION_INPUTS` must not include:
- human preference;
- human ratings;
- reviewer notes;
- competitive challenger scores;
- competitive challenger preference.

The challenger comparison is computed only after the holdout selection is frozen, but before reviewer workspace publication.

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

## Privacy

- local audio paths stay in private evidence only;
- no audio upload;
- no cloud MIR execution;
- reviewer packet must not expose absolute paths, optimizer strategy identity, shadow scores, or challenger preference.

## Authority

- optimizer ranking activation: NO
- PDM training: NO
- release: NO
- deploy: NO
- production activation: NO
- merge: NO without separate `MERGE GO`
