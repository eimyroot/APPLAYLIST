# APPLAYLIST Bundle 52 — Representative Benchmark Corpus R1

## Status

This slice defines the first governed representative optimizer benchmark corpus and explicit engineering acceptance thresholds.

PR #118 is now merged into canonical `feature/bundle-0-bootstrap` at:

`b51c5a42717b605ab65ab7e33f05cbb9a18d2920`

PR #119 has been retargeted onto that canonical lineage. The earlier stacked base on PR #118 head `2f0f5a51a9c71788497a8de0320260e7e86a13bd` is historical evidence only.

This layer is evidence-only. It does not activate an optimizer policy, change Set Intelligence ranking, create a Personal DJ Model, or claim that bounded beam search is musically superior.

## Why this layer exists

A single synthetic case where beam beats greedy is useful proof of capability, but it is not sufficient evidence for policy activation. A benchmark can produce a misleading PASS if it covers only favorable examples.

R1 therefore makes coverage itself part of acceptance.

The corpus cannot PASS unless all required scenario categories are represented and the minimum scenario count is met.

## Required R1 categories

The canonical R1 manifest requires ten categories:

1. `greedy_dead_end`
2. `required_tracks`
3. `phase_transition`
4. `energy_trajectory`
5. `position_locks`
6. `hard_gates`
7. `missing_evidence`
8. `budget_truncation`
9. `high_branching`
10. `alternative_near_duplicate_pressure`

The manifest is versioned as `representative-benchmark-corpus-r1`.

## Acceptance states

The corpus evaluation returns one of:

- `PASS`
- `FAIL`
- `INCOMPLETE`

A known correctness or threshold failure produces `FAIL` even when coverage is also incomplete. Only when no known failure exists can missing categories or too few scenarios resolve to `INCOMPLETE`.

This prevents incomplete coverage from masking an observed regression.

## Default R1 thresholds

The default `optimizer-acceptance-r1` policy requires:

- minimum scenarios: 10
- all ten R1 categories present
- deterministic greedy/beam replay rate: 1.0
- maximum scenario expectation failures: 0
- maximum unexpected missing-evidence events: 0
- maximum unexpected budget-exhaustion events: 0
- minimum explicitly expected beam-win cases: 1
- `activation_authorized = false`

These are engineering correctness and safety thresholds, not musical-quality thresholds.

## Per-scenario expectations

Every scenario carries explicit expectations instead of relying on one aggregate score.

A scenario may define:

- accepted beam statuses,
- expected greedy/beam target reachability,
- whether beam must reach a target that greedy misses,
- minimum required-track completion,
- whether beam may regress required-track completion,
- deterministic replay requirement,
- whether missing evidence is allowed or required,
- whether budget exhaustion is allowed or required,
- minimum beam-pruned candidate count,
- minimum diversity rejection count,
- minimum diverse alternative count.

Expected uncertainty remains truthful. Missing evidence stays explicit as a not-proven state instead of being converted to a neutral score. Expected `BUDGET_EXHAUSTED` remains explicit rather than masquerading as exhaustive failure.

Unexpected missing-evidence or budget-exhaustion events are accounted for across either benchmark strategy, while manifest-required beam-specific expectations remain checked against beam specifically.

## No universal winner score

R1 does not collapse target completion, required tracks, local transition scores, expansion cost, uncertainty, diversity, and runtime boundaries into one scalar.

The existing benchmark remains responsible for separate greedy-vs-beam evidence. The acceptance layer only asks whether explicit engineering invariants and scenario expectations were satisfied.

## Determinism

Both greedy and beam execute deterministic replay checks. R1 raises that property to corpus-level acceptance with:

`minimum_deterministic_replay_rate = 1.0`

A single replay mismatch fails the default acceptance policy.

## Diversity

Alternative diversity remains a post-search evidence selector. R1 can require a near-duplicate-pressure scenario to prove that diversity filtering rejects materially similar alternatives.

This does not alter raw optimizer rank, path objective, TransitionAssessment evidence, or Set Intelligence ranking.

## Activation boundary

Both `OptimizerAcceptanceThresholds` and `RepresentativeCorpusAcceptance` structurally reject `activation_authorized=True`.

Therefore:

`CORPUS_PASS != PRODUCTION_ACTIVATION`

A PASS does not authorize optimizer policy switching, ranking-policy changes, future-feasibility weight activation, Personal DJ Model influence, automatic export, release, or deployment.

## Musical-quality boundary

R1 validates deterministic engineering correctness. It does not establish:

- human DJ preference,
- crowd-response quality,
- genre-specific dramaturgical superiority,
- perceived transition smoothness,
- live-set suitability,
- personal taste fit.

Those require curated real-library evidence and human evaluation.

## Infrastructure boundary

No graph database, vector database, embeddings, or LLM path-selection authority is introduced. The existing persisted adjacency and Set Intelligence contracts remain sufficient for this acceptance slice.

## Next boundary after canonicalization

After PR #119 is separately authorized and canonicalized, the next evidence step is:

`CURATED_REAL_LIBRARY_BENCHMARK_R1 + HUMAN_DJ_REVIEW_PROTOCOL`

Only after that evidence exists should APPLAYLIST consider a new explicitly versioned optimizer/ranking activation policy or any Personal DJ Model influence.
