# Bundle 56 — Desktop Set Proposal Read Model R1

## Status

Implementation slice for issue #127.

Base branch: `feature/bundle-0-bootstrap`  
Exact base SHA: `8d04a174e060456dab33ffc0fd76f2556b7e4bdb`

This bundle is a release-critical dependency for the user-facing Set Proposal / Manual Editor workflow. It does not authorize merge, release, deployment, optimizer activation, or Personal DJ Model training.

## Product value

APPLAYLIST already has canonical Set Intelligence and bounded path optimization, but the current desktop renderer only exposes library import and analysis inspection. The renderer needs a stable, bounded, privacy-safe projection before a Set Proposal screen can consume optimizer results.

The bundle therefore introduces a pure read-model projection:

```text
canonical SetOptimizerResult
  + caller-owned safe track display names
  -> Desktop Set Proposal projection
  -> renderer-safe DTO
  -> future Tauri transport
  -> future Set Proposal Inspector / Manual Editor
```

## New boundary

`services/desktop/set_proposal_projection.py`

The projection is intentionally lossy. It exposes only information required to render an explainable proposal:

- proposal ID,
- optimizer status,
- ranked alternatives,
- ordered track IDs and safe display names,
- phase IDs,
- transition IDs,
- per-step candidate scores,
- bounded path objective summary,
- bounded explanation / warning codes,
- budget / missing-evidence / deterministic-ordering flags,
- explicit non-authorization flags.

## Privacy and security contract

The renderer payload MUST NOT contain:

- filesystem paths,
- provider or provider-version internals,
- `AnalysisEvidence` IDs or evidence refs,
- optimizer input fingerprints,
- intent/root-state/context references,
- arbitrary raw exception or warning text,
- raw domain objects.

Display names are caller-owned renderer labels and must pass fail-closed validation. Absolute POSIX paths, UNC paths, Windows drive paths, control characters, empty values, and oversized values are rejected.

Reason/warning/identifier fields use bounded token validation rather than passing arbitrary domain text through to the renderer.

## Determinism

For an identical immutable `SetOptimizerResult` and equivalent track-ID-to-display-name mapping, the projected DTO is deterministic.

Canonical alternative ranks are preserved exactly. The projection does not re-rank, re-score, mutate, or call Set Intelligence / MIR providers.

## Governance

The DTO always includes:

```text
activation_authorized=false
personal_dj_model_training_authorized=false
```

A successful projection means only that optimizer evidence can be presented safely. It is not provider authority, musical-quality authority, release authority, or production activation evidence.

Human DJ Review R1 remains separately `INCOMPLETE / DEFERRED` until real human review evidence exists.

## Tests

`tests/test_desktop_set_proposal_projection.py` covers:

1. safe ranked projection,
2. deterministic output independent of display-map insertion order,
3. absence of private domain fields from serialized renderer payload,
4. fail-closed missing display labels,
5. fail-closed path/control-shaped display labels,
6. fail-closed unsafe result warning codes,
7. safe projection of `NO_ELIGIBLE_PATH` with zero alternatives.

## Non-scope

This slice deliberately does not add:

- Tauri commands,
- sidecar routes,
- Set Proposal UI,
- playlist revision persistence,
- reorder / lock / replace commands,
- MIR/provider calls,
- new optimization,
- TransitionAssessment mutation,
- human-review completion claims,
- Personal DJ Model training,
- production optimizer activation,
- release or deployment.

## Acceptance

The slice is acceptable only when:

- Python tests and repository quality gates pass on exact PR head,
- renderer payload contains no forbidden private fields,
- unsafe labels/codes fail closed,
- canonical rank order is preserved,
- no existing intelligence contract is weakened,
- no production/release state changes.

## Rollback

Rollback is code-only: remove the projection module, its tests, and this document. There is no data migration, persistence mutation, provider execution, or schema migration.

## Next dependency

Bundle 56B should add the bounded desktop transport and Set Proposal Inspector:

```text
renderer
  -> typed Tauri command
  -> authenticated sidecar/application boundary
  -> canonical optimizer invocation/result source
  -> Desktop Set Proposal projection
  -> renderer-safe proposal
```

Only after that boundary is proven should APPLAYLIST add manual revision commands for accept/reorder/lock/replace and continue toward the R4 Human Editor + Interoperability release slice.
