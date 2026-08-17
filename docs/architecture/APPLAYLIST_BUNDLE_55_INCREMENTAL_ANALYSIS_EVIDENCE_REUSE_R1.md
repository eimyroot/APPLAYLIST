# APPLAYLIST Bundle 55 — Incremental Analysis Evidence Reuse R1

## Status

Implementation slice only. No merge, release, deploy, production activation, optimizer activation, or Personal DJ Model training is authorized by this document.

## Why this exists

APPLAYLIST already has the two primitives required for incremental MIR:

1. canonical content-addressed `TrackIdentity` (`aptrack:v1:sha256:<digest>`), and
2. append-only Bundle 50 `AnalysisEvidenceRecord` persistence.

Re-running the MIR provider for unchanged audio under the same provider/algorithm contract is therefore redundant work. R1 removes that work without creating a second cache database or a second source of truth.

## Reuse rule

A previous successful analysis may be reused only when all of the following are true:

- track identity is canonical content-addressed identity (`aptrack:v1:sha256:<digest>`),
- provider matches exactly,
- canonical analysis version matches exactly,
- provider version matches exactly,
- algorithm version matches exactly,
- the persisted evidence status is `succeeded`.

Any missing identity or identity drift forces fresh provider execution.

Legacy/non-content-addressed track IDs are deliberately not reusable because a path may change bytes while retaining a legacy identifier.

## Execution model

```text
AnalysisJob target
      |
      v
content-addressed TrackIdentity?
      | no ------------------------------> run provider
      |
     yes
      v
provider can prove pre-run execution identity?
      | no ------------------------------> run provider
      |
     yes
      v
latest successful evidence exact-match?
      | no ------------------------------> run provider -> append evidence
      |
     yes
      v
reuse existing evidence_id
      |
      v
record target success in current AnalysisJob
```

A reuse hit does not append a duplicate evidence row. Job history remains explicit because the new AnalysisJob target outcome references the previously persisted evidence ID.

## Resume semantics

Because successful evidence is persisted per target, a new job after cancellation/interruption can reuse already completed exact evidence and execute the provider only for remaining or invalidated targets.

This is crash/restart reuse through durable evidence, not in-memory memoization.

## Provider identity

`RoutedAnalysisService.execution_identity()` is optional and fail-closed.

- the versioned baseline librosa provider can expose a pre-run identity from the installed librosa package version, canonical analysis version, and `BaselineLibrosaMIR.algorithm_version`;
- providers that cannot prove a stable identity before execution return `None` and are never reused in R1.

Provider/algorithm configuration changes that alter analysis semantics must advance the versioned algorithm identity before they are eligible for reuse.

## Security and truth boundaries

R1 does not:

- infer file equality from path alone,
- trust workbook/inventory `File Signature` as content SHA-256,
- mutate historical analysis evidence,
- reuse failed evidence,
- bypass provider validation,
- change `TransitionAssessment` authority,
- activate optimizer/ranking behavior,
- train the Personal DJ Model,
- expose local filesystem paths to Music DNA.

## Performance expectation

The architecture changes warm-run cost from approximately:

```text
N unchanged tracks -> N provider executions
```

into:

```text
N unchanged tracks -> N cheap evidence lookups -> 0 provider executions
```

Only new content or analysis-identity drift triggers expensive MIR.

## Follow-up boundary

Bundle 54 is a real-library benchmark bridge and currently performs direct audio hashing/MIR outside the reusable Bundle 50 AnalysisJob path. A later governed slice should consume/reconcile canonical reusable analysis evidence (and, where appropriate, seed it from verified private runtime evidence) so real-library benchmark reruns do not repeat full MIR work.

That follow-up must preserve the Bundle 54 rule that real content SHA-256 comes from actual bytes and must not reinterpret the historical opaque inventory `File Signature` as a cryptographic digest.
