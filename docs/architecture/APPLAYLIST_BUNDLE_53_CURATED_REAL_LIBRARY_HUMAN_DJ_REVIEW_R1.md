# APPLAYLIST Bundle 53 — Curated Real-Library Benchmark R1 + Human DJ Review Protocol

## Status

This slice defines the first governed human-evaluation layer for APPLAYLIST set planning.

It is based on canonical `feature/bundle-0-bootstrap` after PR #119 and does not activate any optimizer, ranking policy, Personal DJ Model, preference-learning loop, release, or deployment path.

The implementation provides contracts and evaluation runtime only. It does **not** claim that a real local DJ library has already been ingested or reviewed. A later pilot must supply a real curated `CuratedLibrarySnapshot`, real optimizer path evidence, and actual blinded DJ reviews.

## Why this layer exists

Representative synthetic scenarios can prove engineering correctness, determinism, bounded-search truthfulness, and hard-gate behavior. They cannot establish whether a proposed set feels musically convincing to a DJ.

Human evidence is therefore required before APPLAYLIST considers any optimizer/ranking activation or Personal DJ Model influence.

The human layer is deliberately separate from the engineering acceptance layer:

- engineering evidence answers: **is the system behaving according to its contracts?**
- human evidence answers: **how do concrete set plans feel to a DJ under blinded review?**

Human preference may never override a failed engineering hard gate.

## Real-library snapshot boundary

A `CuratedLibrarySnapshot` is immutable identity/evidence for the actual library used in the review.

R1 requires:

- stable `snapshot_id` and `snapshot_version`,
- a library fingerprint,
- explicit track IDs,
- an explicit generation time,
- evidence references.

A curated review case may reference only tracks present in that snapshot.

No fake/default tracks are introduced when a local library is unavailable.

## Required dramaturgical coverage

R1 uses six broad set roles:

1. `opening`
2. `build`
3. `mid_set`
4. `peak`
5. `reset`
6. `closing`

The default protocol requires at least 12 cases and coverage of every role.

These are review-coverage roles, not genre labels and not ranking weights.

## Concrete review plans

Human review operates on concrete path evidence, not aggregate benchmark scores.

`ReviewableSetPlan` records:

- strategy identity in governance evidence,
- optimizer result ID,
- path ID,
- ordered track IDs,
- transition IDs,
- evidence references.

The helper `reviewable_plan_from_alternative(...)` projects an immutable `SetPathAlternative` into this review form without changing the optimizer result.

## Blind A/B assignment

Every `CuratedReviewCase` contains one greedy plan and one bounded-beam plan.

`build_blinded_plan_assignment(...)` deterministically maps those plans into anonymous `PLAN_A` and `PLAN_B` slots from:

- protocol version,
- case identity,
- scenario fingerprint,
- explicit blinding seed.

The mapping is retained as governance evidence but must not be shown in the reviewer-facing interface while the judgement is made.

R1 structurally rejects assignments or reviews that state algorithm identity was visible.

The blinding seed is for reproducible assignment, not secrecy. Reviewer-facing identity separation is the relevant protection.

## Human review dimensions

R1 keeps musical judgements separate instead of collapsing them into one scalar:

1. `transition_smoothness`
2. `phrase_alignment`
3. `energy_flow`
4. `dramaturgical_fit`
5. `set_coherence`
6. `alternative_usefulness`

Each dimension records a 1–5 score for both anonymous plans.

The reviewer also records one pairwise preference:

- `PLAN_A`
- `PLAN_B`
- `TIE`
- `ABSTAIN`

`TIE` and `ABSTAIN` are valid evidence. The protocol must not force a winner when the reviewer cannot justify one.

## Confidence and evidence

A review records:

- reviewer reference,
- confidence in `[0, 1]`,
- observation time,
- optional reason codes,
- evidence references.

The reviewer reference should be stable and privacy-appropriate; it need not expose personal identity in exported benchmark evidence.

## Protocol PASS meaning

`HumanReviewProtocolVerdict.PASS` means only that the named R1 evidence surface is complete and structurally trustworthy.

Default R1 protocol thresholds require:

- at least 12 curated cases,
- at least one review per case,
- all six set roles,
- reviewed-case fraction = 1.0,
- blind-integrity rate = 1.0,
- full six-dimension coverage rate = 1.0,
- zero engineering regressions.

A PASS does **not** mean:

- bounded beam is universally musically superior,
- the ranking policy should switch,
- a production optimizer is authorized,
- crowd response has been proven,
- genre-specific dramaturgy has been solved,
- Personal DJ Model training is authorized.

## Human preference aggregation

The evaluator reports separately:

- greedy preference count,
- beam preference count,
- tie count,
- abstain count,
- per-dimension greedy mean,
- per-dimension beam mean,
- per-dimension beam-minus-greedy difference.

There is no universal musical-quality score and no automatic winner threshold in R1.

This prevents musical quality, search cost, hard constraints, uncertainty, and personal taste from being hidden behind one scalar.

## Engineering non-override rule

Every curated case carries explicit `engineering_acceptance_passed` evidence.

If engineering regression count exceeds the allowed threshold, the human protocol verdict is `FAIL` even if every reviewer prefers the affected plan.

This is a hard governance rule:

`HUMAN_PREFERENCE != HARD_GATE_OVERRIDE`

## Personal DJ Model boundary

Human review data is valuable future preference evidence, but R1 explicitly does not train or update a Personal DJ Model.

Before any learning layer may consume human reviews, APPLAYLIST needs a separate versioned policy covering at least:

- explicit opt-in,
- immutable raw feedback retention,
- separation of observation from inferred preference,
- reversible model/profile updates,
- minimum evidence volume,
- contradiction handling,
- user-visible explanations,
- rollback/reset semantics.

Until then:

`HUMAN_REVIEW_EVIDENCE != PERSONAL_DJ_MODEL_TRAINING_AUTHORIZATION`

## Current execution boundary

This code makes the review protocol executable and testable, but a genuine real-library benchmark still requires evidence that is not available inside this GitHub-only runtime:

1. capture a real local APPLAYLIST library snapshot,
2. select representative tracks/cases from that snapshot,
3. run greedy and bounded-beam planners on identical inputs,
4. preserve concrete path IDs and transition evidence,
5. generate blind A/B assignments,
6. render or otherwise expose plans to a DJ without algorithm labels,
7. record actual reviews,
8. run the R1 evaluator,
9. archive the report and raw review evidence in CASER.

No synthetic unit-test fixture may be presented as completion of steps 1–9.

## Infrastructure boundary

R1 requires no graph database, vector database, embeddings, cloud recommendation service, or LLM planning authority.

The current local-first persisted intelligence graph and deterministic optimizer remain sufficient.

## Acceptance gates for this implementation slice

The code slice is acceptable when:

- contracts are immutable/fail-closed,
- blind assignment is deterministic,
- assignments reference exactly the two plans in a case,
- cases cannot reference tracks outside the snapshot,
- full-review protocol can PASS integrity without authorizing activation,
- missing real-library coverage is `INCOMPLETE`,
- dimension gaps fail closed,
- engineering regression beats unanimous human preference,
- visible algorithm identity is rejected,
- activation flags are structurally rejected,
- existing test suite remains green.

## Next evidence step after canonicalization

After this protocol slice is merged, the next real evidence operation is:

`LOCAL_LIBRARY_SNAPSHOT_R1 -> CURATED_CASE_SELECTION -> BLINDED_HUMAN_DJ_PILOT`

Only after actual real-library human evidence exists should APPLAYLIST discuss an explicitly versioned optimizer/ranking activation decision or Personal DJ Model learning policy.
