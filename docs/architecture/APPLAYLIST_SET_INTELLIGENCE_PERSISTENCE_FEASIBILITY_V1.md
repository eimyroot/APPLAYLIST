# APPLAYLIST Set Intelligence Persistence + Feasibility v1

## Status

Governed R2.5 implementation slice after Set Intelligence runtime v1 and before Bundle 52 graph/path optimization.

This slice does not authorize canonicalization, merge, release, deploy, graph database adoption, vector database adoption, desktop exposure, or optimizer activation.

## Purpose

The graph optimizer needs durable and reproducible inputs before it needs a sophisticated search algorithm.

This slice therefore adds three bounded capabilities:

1. immutable persistence for context-specific TransitionAssessment snapshots and SequenceState revisions,
2. explicit SetPhase -> TransitionContext mapping with no hidden musical presets,
3. bounded future required-track reachability that distinguishes impossibility from incomplete proof.

## Dependency reality

At implementation start:

- PR #112 was merged into canonical `feature/bundle-0-bootstrap`,
- PR #113 had been merged into its dependency feature branch rather than canonical,
- PR #114 had been merged into the #113 lineage rather than canonical,
- the integrated R2.5 dependency snapshot used by this slice is `bdbe90f2102932e3e8b57e1aedfa5aeede0a07a0`.

This branch does not silently reconcile that lineage into canonical. Canonicalization remains a separate merge authorization boundary.

## Persistence model

APPLAYLIST already has governed SQLite repository patterns. This slice reuses `data.connection.get_sqlite_connection()` and introduces no storage dependency.

```text
Transition relation identity
  transition_id
        |
        + context_id + context_version
        v
immutable TransitionAssessment snapshot
        |
        + source adjacency index
        + target adjacency index

SequenceState
  state_id + state_version
        v
immutable sequence-state revision
```

### Why a transition snapshot key includes context

Runtime v1 currently carries `ContextualTransitionProjection` and context-filtered strategy candidates inside `TransitionAssessment`, while `transition_id` itself identifies the underlying source/target relation and does not include context.

Persisting by `transition_id` alone would therefore permit one context projection to overwrite or collide with another legitimate projection.

V1 persistence solves this by assigning a deterministic assessment snapshot identity from:

```text
transition_id | context_id | context_version
```

The underlying `transition_id` remains available for graph relation identity and adjacency.

### Immutability

For both transition snapshots and sequence-state revisions:

- payloads use deterministic sorted JSON,
- SHA-256 is stored with the payload,
- reads verify SHA-256 before decoding,
- identical append is idempotent,
- same immutable identity with different payload fails closed,
- there is no update/delete authority in this repository slice.

## Phase -> TransitionContext mapping

The mapping policy is `phase-transition-context-v1`.

The caller supplies an explicit base `TransitionContext`.

A phase may only narrow hard transition-strategy eligibility through its explicit `forbidden_transition_strategies`.

The mapper does **not** invent or silently modify:

- tempo-change limits,
- minimum harmonic fit,
- phrase-evidence requirements,
- transition weights,
- energy direction,
- transition goal.

`preferred_transition_strategies` remain Set Intelligence soft preferences. They are not converted into hard transition gates.

The mapped context receives deterministic phase-scoped identity/version provenance.

## Bounded future feasibility

The first evaluator is intentionally a proof-oriented bounded reachability layer, not the Bundle 52 optimizer.

It traverses persisted outgoing transition snapshots in deterministic order and may enforce:

- accepted explicit TransitionContext identity/version,
- transition projection must be unblocked and scored,
- forbidden tracks,
- repeat policy,
- explicit track scope,
- include/exclude tag scope when tag evidence is supplied,
- fixed future position locks,
- floating lock tracks as future obligations,
- target-duration ceiling when per-track duration evidence is supplied,
- remaining required tracks.

The search budget is explicit:

```text
FeasibilityPolicy
├── policy_version
├── max_depth          <= 16
└── max_expanded_states <= 100000
```

### Truth-preserving outcomes

```text
REACHABLE
  complete bounded proof found

INFEASIBLE
  supported frontier was exhaustively consumed without satisfying obligations

NOT_PROVEN_WITHIN_BUDGET
  depth/state budget truncated a still-possible proof

NOT_PROVEN_MISSING_EVIDENCE
  required duration/tag/candidate evidence was absent

NOT_PROVEN_UNSUPPORTED_CONSTRAINT
  reserved for an active constraint the v1 evaluator cannot soundly prove
```

Only `REACHABLE` maps to score `1.0` and only proved `INFEASIBLE` maps to `0.0`. Not-proven states carry no score.

## Ranking boundary

This slice does **not** silently enable `future_feasibility` in the existing `balanced_set_ranking_policy_v1`.

The existing Set Intelligence ranking behavior remains unchanged. A later explicit policy version may consume feasibility results after benchmarking.

This prevents a new planning heuristic from changing candidate rankings merely because persistence became available.

## Bundle 52 readiness gate

Before the first bounded beam/lookahead optimizer is started, the intended gate is:

```text
immutable transition adjacency          PASS
immutable sequence-state persistence    PASS
explicit phase/context mapping          PASS
bounded feasibility semantics           PASS
truthful not-proven states               PASS
regression + CI                          PASS
canonical lineage reconciliation         SEPARATE AUTHORIZATION
```

## Explicit non-goals

- no graph/path optimizer runtime,
- no greedy/beam path winner activation,
- no Neo4j or graph DB,
- no vector DB,
- no embeddings,
- no new MIR provider,
- no Set Intelligence ranking-policy activation change,
- no first-track seeding,
- no renderer/Tauri command,
- no release/signing/notarization/deploy,
- no automatic canonical merge.
