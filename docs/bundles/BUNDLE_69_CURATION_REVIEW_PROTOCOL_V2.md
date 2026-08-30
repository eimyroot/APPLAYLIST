# Bundle 69 — Curation Review Protocol V2 + Holdout-Safe Calibration

## Why this bundle exists

Skill Tester found that the legacy six-dimension Human DJ Review mixed two different experimental questions:

1. is this a good **set sequence / curation plan**?
2. did the DJ happen to perform a **smooth transition** this time?

The legacy reviewer workspace showed Plan A/B track ordering while requiring `transition_smoothness` and `phrase_alignment`, but did not bind a standardized mix recipe or rendered transition. Bundle 68 then used the single overall human preference as calibration truth for the Bundle 67 curation challenger.

That creates execution contamination.

The same original 12 cases also influenced Bundle 65/67 design, so they are development evidence rather than independent validation.

## Core rule

`CURATION_REVIEW != TRANSITION_FEASIBILITY_REVIEW != HUMAN_EXECUTION_REVIEW`

Bundle 69 implements the curation side only.

## Curation Review V2

New protocol:

- `protocol_version = curation-review-v2`
- `audition_mode = sequence_curation_only`
- explicit execution-quality exclusion acknowledgement
- separate V2 packet/submission schema and fingerprint
- legacy Bundle 63 submission schema rejected

Required dimensions, Plan A and B scored 1..5:

1. `energy_flow`
2. `dramaturgical_fit`
3. `set_coherence`
4. `alternative_usefulness`
5. `track_selection_fit`

Case outcome:

- `plan_a`
- `plan_b`
- `tie`
- `abstain`

Human preference is explicit and is never derived from dimension sums.

`transition_smoothness` and `phrase_alignment` are not Curation Review V2 dimensions.

## Transition evidence

Transition feasibility remains a separate future evidence stream.

Until APPLAYLIST supplies a deterministic transition proposal or immutable standardized preview, transition review should be represented as not assessable rather than a forced numeric score.

No transition or execution data enter the V3 curation calibration API.

## Evidence roles

### development_calibration

The existing R2 12-case set is permanently treated as development/calibration evidence because its qualitative failures directly influenced Bundle 65/67.

It may support personal-DJ calibration and debugging, but not independent validation or a general superiority claim.

### holdout_validation

A fresh holdout requires a frozen manifest before human labels exist.

The manifest binds:

- selected case IDs and scenario fingerprints
- source snapshot
- case-selection policy and seed commitment
- source optimizer SHA
- challenger SHA/policy/config digest
- calibration policy digest
- source evidence revisions
- set-role coverage
- label-unavailable-at-freeze assertion

Changing candidate/config/threshold identity after labels invalidates the binding for the changed candidate.

## Selection scope

### representative_holdout

Selection cannot depend on human labels, challenger score, challenger preference, or favorable source/challenger disagreement.

This is the only scope that may set `representative_performance_claim_allowed=true`.

### diagnostic_challenge_set

May intentionally select hard/disagreement/failure cases.

It is diagnostic only and cannot be represented as representative performance.

## Survivorship protection

Once a representative holdout is frozen, every selected case stays in the denominator.

System outcomes:

- `reviewable_pair`
- `technically_identical_pair`
- `no_meaningful_alternative`
- `missing_required_evidence`
- `source_generation_failed`
- `challenger_not_proven`

Only `reviewable_pair` may receive a human A/B review.

A non-reviewable system outcome must not be rewritten as human `abstain`.

The report exposes:

- selected case count
- reviewable pair count
- non-reviewable system outcome count
- human reviewed case count
- reviewable pair fraction
- meaningful alternative availability rate
- per-outcome counts

Poor complete product evidence yields negative evidence, not hidden case deletion.

## Personal vs multi-DJ scope

### personal_dj_calibration

One genuine reviewer may calibrate the challenger against that DJ's preferences.

This is not a market-wide claim.

### multi_dj_product_evaluation

Requires policy-defined independent reviewer coverage; R1 defaults to three reviewer identities before this scope can be complete.

A/B placement must be counterbalanced and reviewer-specific. Reviewer disagreement remains visible through pooled, macro/per-reviewer and disagreement metrics.

## Bounded verdicts

Bundle 69 reuses the bounded calibration vocabulary:

- `INCOMPLETE`
- `DOES_NOT_SUPPORT_ACTIVATION`
- `SUPPORTS_FURTHER_EVALUATION`

For development evidence, `SUPPORTS_FURTHER_EVALUATION` means only that a fresh holdout is justified.

It does not mean validated superiority and never authorizes optimizer activation.

## Skill Tester attack history

The design was attacked before implementation for:

1. transition execution contamination;
2. old/new packet schema ambiguity;
3. personal vs general reviewer scope confusion;
4. underspecified alternative usefulness;
5. missing structural contamination invariant;
6. development/holdout circular validation;
7. challenger-dependent holdout selection bias;
8. A/B slot position bias;
9. survivorship bias from dropping weak/unreviewable system outcomes;
10. hidden multi-DJ disagreement.

Protocol V2.4 received `PASS_FOR_IMPLEMENTATION_DESIGN` before this implementation branch was opened.

## Non-claims

- `independent_validation=true` means independent holdout-case validation under this protocol, not independent laboratory replication.
- three reviewers is a bounded minimum for product-evaluation scope, not universal statistical proof.
- no p-value, significance, or market-wide accuracy claim is emitted.
- personal-DJ calibration remains personal.

## Privacy / security

The new protocol/calibration services are pure over supplied evidence:

- no audio reads
- no MIR/provider execution
- no filesystem persistence
- no network/cloud upload
- no hidden telemetry
- no TransitionAssessment mutation
- no optimizer/ranking mutation

## Authority

- `MERGE_AUTHORIZATION=NO`
- `OPTIMIZER_RANKING_ACTIVATION=NO`
- `RELEASE_AUTHORIZATION=NO`
- `DEPLOY_AUTHORIZATION=NO`
- `PRODUCTION_ACTIVATION=NO`
- `PDM_TRAINING=NO`
