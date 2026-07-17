# Bundle 25 — Fail-Closed Provider Result Contract

## Goal

Introduce one canonical, validated result boundary between optional audio providers and all downstream APPLAYLIST components.

Bundle 25 does not enable provider mode in the API, jobs or persistence. The legacy analyzer remains the default path.

## Source Audit

### PR #20

The canonical MIR concept is useful, but the branch is not safe to merge:

- its adapter depends on a providers module absent from that commit,
- a flat string key without confidence can call `.get()` on a string,
- its PR Guard did not pass.

Bundle 25 reimplements the useful contract independently and includes regressions for both P1 defects.

### PR #22

The branch title claims real Essentia extraction, but both provider implementations still return `status="stub"`.

The branch also contains broad historical changes, duplicate `* 2.py` files, tracked production-style environment configuration and unresolved security/data-flow defects. It must not be merged or cherry-picked as a whole.

## Contract

Validated canonical fields:

- path,
- provider,
- bpm,
- bpm confidence,
- key,
- key confidence,
- energy,
- loudness,
- duration,
- genre hint,
- analysis status,
- analysis schema version.

Accepted success statuses are normalized to `ok`:

- `ok`,
- `success`,
- `completed`.

Any other status, including `stub`, is rejected as `provider_output_invalid`.

## Error Taxonomy

- `provider_unknown`
- `provider_unavailable`
- `provider_runtime_error`
- `provider_output_invalid`

Errors retain provider identity when available and are raised before any persistence boundary.

## Validation Rules

- raw output must be a mapping,
- provider identity must be present and must match the selected provider,
- nested beat/key/metrics/tags blocks must be mappings,
- numeric fields must be finite,
- BPM must be between 20 and 400,
- confidence and energy values must be between 0 and 1,
- duration must not be negative,
- text fields must have bounded length,
- optional fields may remain null,
- flat key strings without confidence are valid.

## Execution Boundary

```text
provider selector
  -> provider execution
  -> canonical normalization
  -> contract validation
  -> CanonicalAnalysisResult
```

Persistence is intentionally outside Bundle 25. A later routed-analysis slice may persist only `CanonicalAnalysisResult` values after explicit conversion to the storage schema.

## Security and Failure Behavior

- optional audio libraries are not imported by the contract or service modules,
- provider crashes are converted to controlled runtime errors,
- provider selection failures remain explicit,
- stub providers fail closed,
- no silent fallback changes the selected provider,
- no database or public API contract is changed.

## Verification

Required gates:

- existing test suite remains green,
- nested and flat payload normalization,
- regression for flat key without confidence,
- malformed nested block rejection,
- non-finite and out-of-range number rejection,
- stub rejection,
- provider identity mismatch rejection,
- runtime failure translation,
- provider selection error preservation,
- boot-safe import test,
- Python 3.11 and 3.12 CI matrix.

## Rollback

Before merge, close the Bundle 25 pull request or delete its feature branch. After merge, revert its squash commit. No database rollback is required.
