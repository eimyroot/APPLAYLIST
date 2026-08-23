# Bundle 69 — Human Review Protocol R2 Isolation + Curation Calibration R3

## Why this bundle exists

Skill Tester issue #159 found that Human DJ Review R1 mixed two different questions:

1. Is this a good ordered set / curation choice?
2. Did the DJ happen to execute the transition well this time?

The R1 workspace required `transition_smoothness` and `phrase_alignment` without a standardized transition execution recipe or deterministic rendered preview. Bundle 68 then compared the single overall human preference with the Bundle 67 curation challenger. That made curation calibration vulnerable to execution noise.

Issue #162 redesigned the protocol. Three independent adversarial design passes were completed before implementation. The final R2.2 design additionally treats the historical 12 cases as development/regression evidence rather than independent validation because their qualitative findings influenced Bundle 67.

## Core invariant

`CURATION_REVIEW != TRANSITION_FEASIBILITY_REVIEW != HUMAN_EXECUTION_REVIEW`

## Additive-only migration

Bundle 69 does not modify Bundle 63/R1 or Bundle 68/R2 code. Historical R1 evidence keeps its original meaning.

New contracts are introduced under `human-dj-review-r2`, preregistration/binding R2/R3 contracts, and `curation-calibration-r3`.

## CurationReviewR2

Formal curation review contains only:

- energy flow;
- dramaturgical fit;
- set coherence;
- alternative usefulness;
- explicit A/B/tie/abstain curation preference;
- confidence;
- prior case exposure;
- sequence-only judgment mode;
- assertions about transition execution/preview use and blind integrity.

A contaminated review is preserved as evidence but is not eligible for clean holdout calibration.

Explicit human preference is never rewritten from dimension arithmetic.

## Immutable clean attestation

A review is not treated as clean merely because convenient defaults say `no exposure` or `no transition execution`.

Formal calibration additionally requires a separate `CurationCleanAttestationR2` bound to:

- exact `review_id`;
- exact `curation_session_id`;
- prior case exposure;
- judgment mode;
- transition execution used/not used;
- transition preview heard/not heard;
- algorithm identity hidden status;
- observed timestamp.

The calibration service requires exact fact equality between review and attestation. A mismatch fails closed.

`CurationCalibrationBindingR3` then persists the deterministic attestation fingerprint together with the case/review/session identity and frozen selection-manifest fingerprint. The final calibration report requires one exact binding for every evidence row and includes those bindings in its report identity.

This prevents an untraceable runtime boolean from becoming the authority for clean-holdout eligibility.

## Holdout isolation

`HoldoutCaseSamplingPolicy` is frozen before case generation and contains:

- canonical SHA;
- snapshot/scope fingerprints;
- deterministic seed;
- case-generator version;
- role quotas;
- frozen fallback capacity.

`select_holdout_cases_r2(...)` accepts only the policy and technical candidate metadata. It has no input for shadow scores, challenger preference, human ratings or human labels.

The selection ledger preserves selected/rejected/fallback provenance.

The original 12 reviewed cases are `development_regression`; they cannot count as clean personal/general holdout evidence.

## Frozen replacement policy

Fallback replacement is also preregistered rather than supplied as a mutable call-time allowlist.

`HoldoutReplacementPolicyR2` binds:

- frozen selection manifest fingerprint;
- preregistration manifest fingerprint;
- frozen timestamp;
- exact allowed technical-invalidity reason codes;
- policy version.

Replacement can only select the next case from the already-frozen fallback order and only for an allowed technical reason. Preference/challenger-like reason vocabulary is rejected by the policy contract.

The final report binds the deterministic replacement-policy fingerprint into its report identity.

## Transition isolation

`TransitionReviewSpecR2` binds:

- outgoing/incoming track + segment identity;
- analysis revisions;
- evidence fingerprints;
- canonical second-based mix windows;
- optional beat-grid revision;
- duration;
- exact target BPM or explicit unchanged tempo;
- strategy id/version;
- technique policy;
- evidence refs.

Every change changes the deterministic transition spec fingerprint.

Transition feasibility dimensions are separate:

- phrase-window feasibility;
- energy handoff feasibility;
- spectral compatibility evidence;
- tempo feasibility;
- harmonic compatibility;
- transition strategy suitability;
- vocal collision risk.

Each is either assessable with evidence refs or explicit `not_assessable` with a reason. Vocal collision is never inferred when explicit vocal evidence is missing.

Human transition audition requires a deterministic rendered preview fingerprint or standardized execution recipe fingerprint.

## Human execution isolation

`HumanExecutionReviewR2` is a separate evidence type. It is not imported by the curation calibration service and cannot authorize activation.

## CurationCalibrationR3

The case-calibration function consumes only:

- source case binding;
- blind assignment;
- CurationReviewR2;
- immutable CurationCleanAttestationR2;
- Bundle 67 ShadowPathComparison.

Transition and execution artifacts are not accepted as inputs.

The report additionally requires:

- exact calibration bindings for every evidence row;
- frozen holdout selection;
- frozen HoldoutReplacementPolicyR2;
- preregistration-manifest fingerprint;
- versioned calibration policy.

Clean evidence outside the frozen selected holdout fails closed. A personal holdout case may contribute at most one clean review, so changing `review_id` cannot inflate sample size. Missing selected clean cases keep the verdict `INCOMPLETE`.

For personal-DJ calibration:

- only clean `personal_holdout` reviews count;
- development/regression cases are excluded;
- abstains are excluded from accuracy denominators;
- ties remain first-class evidence;
- exact and decisive agreement are reported;
- 95% Wilson intervals are reported;
- policy gates use Wilson lower bounds, not point estimates alone;
- all six set roles are required;
- default clean-case floor is 24;
- no verdict above `supports_further_evaluation` exists.

The personal analyzer rejects `general_dj_product_validation`; general validation requires a separately pre-registered cluster-aware analyzer so repeated multi-DJ rows are not incorrectly treated as independent observations.

## Skill Tester invariants encoded as tests

Tests cover, among other cases:

- R1 dimensions cannot satisfy R2;
- immutable attestation must exactly bind review/session facts;
- development cases cannot become clean holdout evidence;
- manual transition execution contaminates/excludes curation review;
- prior case exposure excludes clean holdout evidence;
- A/B inversion preserves source strategy identity;
- numeric dimension arithmetic does not rewrite explicit preference;
- shadow path identity mismatch fails closed;
- holdout selection is deterministic and input-order independent;
- replacement policy is frozen and bound to the exact selection manifest;
- frozen fallback order cannot be bypassed;
- transition spec fingerprint changes on bound window changes;
- missing vocal evidence is `not_assessable`;
- tempo/harmonic feasibility stay independent;
- human transition audition requires preview/recipe evidence;
- every calibration evidence row must have an exact immutable calibration binding;
- clean evidence must belong to the frozen holdout;
- the same case cannot inflate personal holdout `n` with multiple review IDs;
- complete clean 24-case personal holdout can support only further evaluation;
- Wilson lower bounds, not point estimates, drive the policy gate;
- general claims cannot use the personal independent-row analyzer;
- near-equivalent cases remain diagnostic evidence;
- activation authority remains false.

## Privacy / execution boundary

Bundle 69 is pure contract/in-memory logic:

- no audio reads;
- no MIR provider execution;
- no network calls;
- no cloud upload;
- no filesystem persistence;
- no hidden telemetry.

## Authority

- release: NO
- deploy: NO
- production activation: NO
- optimizer ranking activation: NO
- PDM training: NO
- merge: NO until separate explicit `MERGE GO`
