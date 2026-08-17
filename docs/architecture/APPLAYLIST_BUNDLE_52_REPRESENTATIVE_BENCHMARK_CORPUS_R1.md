# APPLAYLIST Bundle 52 — Representative Benchmark Corpus R1

## Status

This slice defines the first governed representative optimizer benchmark corpus and explicit engineering acceptance thresholds.

It is stacked on PR #118 exact head `2f0f5a51a9c71788497a8de0320260e7e86a13bd` because PR #118 has not been authorized for merge.

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

The manifest is versioned as:

`representative-benchmark-corpus-r1`

## Acceptance states

The corpus evaluation returns one of:

- `PASS`
- `FAIL`
- `INCOMPLETE`

`INCOMPLETE` is deliberately distinct from `FAIL`.

An incomplete corpus means the evidence surface is insufficient to make the engineering acceptance claim. Missing categories or too few scenarios can never be interpreted as PASS.

## Default R1 thresholds

The default `optimizer-acceptance-r1` policy requires:

- minimum scenarios: 10
- all ten R1 categories present
- deterministic greedy/beam replay rate: 1.0
- maximum scenario expectation failures: 0
- maximum unexpected missing-evidence events: 0
- maximum unexpected budget-exhaustion events: 0
- minimum expected beam-win cases: 1

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

This allows expected uncertainty to remain truthful. For example, the missing-evidence case must observe missing evidence and should resolve to `NOT_PROVEN_MISSING_EVIDENCE`; that expected unknown state is not an acceptance failure.

Likewise, the budget-truncation case explicitly requires `BUDGET_EXHAUSTED`. The test is not asking the optimizer to hide truncation; it is verifying that the bounded-search contract reports it correctly while preserving valid partial alternatives.

## No universal winner score

R1 does not collapse target completion, required tracks, local transition scores, expansion cost, uncertainty, diversity, and runtime boundaries into one scalar.

The existing benchmark remains responsible for separate greedy-vs-beam evidence.

The acceptance layer asks whether explicit engineering invariants and scenario expectations were satisfied.

## Determinism

Both greedy and beam benchmark strategies already execute deterministic replay checks in PR #118.

R1 raises that property to corpus-level acceptance:

`minimum_deterministic_replay_rate = 1.0`

A single replay mismatch fails the default acceptance policy.

## Diversity

Alternative diversity remains a post-search evidence selector.

R1 can require a near-duplicate-pressure scenario to prove that diversity filtering actually rejects at least one materially similar alternative.

This does not alter raw optimizer rank, path objective, TransitionAssessment evidence, or Set Intelligence ranking.

## Missing evidence

Missing evidence is never converted into an invented neutral value.

Scenario expectations distinguish:

- expected missing evidence,
- allowed missing evidence,
- unexpected missing evidence.

Unexpected missing evidence counts toward corpus failure under the default policy.

Expected missing evidence remains explicit evidence of correct fail-open/fail-unknown semantics rather than being mislabeled as optimizer failure.

## Budget truncation

Expected bounded-search truncation is a first-class scenario category.

Unexpected truncation is a corpus acceptance failure under the default policy.

The dedicated budget scenario, however, must demonstrate the opposite: the optimizer must truthfully expose `BUDGET_EXHAUSTED` rather than pretending that the explored frontier was exhaustive.

## Activation boundary

Both `OptimizerAcceptanceThresholds` and `RepresentativeCorpusAcceptance` structurally reject `activation_authorized=True`.

Therefore:

`CORPUS_PASS != PRODUCTION_ACTIVATION`

A PASS means only that the named R1 engineering corpus and thresholds were satisfied.

It does not authorize:

- optimizer policy switching,
- ranking-policy changes,
- future-feasibility weight activation,
- Personal DJ Model influence,
- automatic export,
- release,
- deployment.

## Musical-quality boundary

R1 uses deterministic synthetic/evidence-backed scenario semantics to validate engineering correctness.

It does not establish:

- human DJ preference,
- crowd-response quality,
- genre-specific dramaturgical superiority,
- perceived transition smoothness,
- live-set suitability,
- personal taste fit.

Those require later curated real-library benchmark evidence and human evaluation.

## Infrastructure boundary

No graph database, vector database, embeddings, or LLM path-selection authority is introduced.

The existing persisted SQLite adjacency and Set Intelligence contracts remain sufficient for this acceptance slice.

## Next boundary after canonicalization

After PR #118 and this stacked corpus slice are explicitly canonicalized, the next evidence step should be:

`CURATED_REAL_LIBRARY_BENCHMARK_R1 + HUMAN_DJ_REVIEW_PROTOCOL`

Only after that evidence exists should APPLAYLIST consider a new explicitly versioned optimizer/ranking activation policy or any Personal DJ Model influence.
