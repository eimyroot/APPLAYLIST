# Bundle 68 — Human Preference Calibration R2

## Purpose

Bundle 67 introduced a shadow-only Competitive Curation challenger. Bundle 68 defines how that challenger is evaluated against genuine blinded DJ judgments before any optimizer-authority discussion.

The governing principle is:

> `HUMAN AGREEMENT EVIDENCE != OPTIMIZER ACTIVATION`

Even a perfect calibration result can only support further evaluation. It cannot authorize ranking changes, production activation, release, deployment, or Personal DJ Model training.

## Inputs

R2 binds four already-versioned evidence objects:

1. `CuratedReviewCase`
2. `BlindedPlanAssignment`
3. genuine `HumanDJReview` from the Bundle 63 blinded protocol
4. Bundle 67 `ShadowPathComparison`

The human review must already exist before the blind assignment is resolved back to source strategy identity.

## Blind integrity

Human judgment is recorded as:

- `plan_a`
- `plan_b`
- `tie`
- `abstain`

Only calibration resolves Plan A / Plan B back to the source `greedy` or `beam` plan. The assignment must bind exactly to the two plans in the source case, and the shadow comparison must bind exactly to the two corresponding source path IDs.

Any mismatch fails closed.

## Outcome semantics

### Human decisive preference

`greedy` or `beam` after blind resolution.

### Human tie

A real signal that neither plan is materially preferable. A challenger that invents a winner on a human tie is recorded as a false winner.

### Human abstain

Preserved as an abstention and excluded from accuracy denominators. It never becomes a tie or loss.

### Challenger not-proven

Preserved as `not_proven`. It is not silently converted to a tie.

## Metrics

The report exposes:

- case count
- reviewed case count / fraction
- decisive human judgment count
- abstain count
- exact agreement count/rate
- decisive agreement count/rate
- confidence-weighted decisive agreement
- human tie count
- challenger tie count
- false-winner-on-human-tie count/rate
- challenger-tie-on-human-decisive count
- set-role coverage
- confusion matrix
- per-case evidence and reason codes

Confidence weighting is transparent: decisive review confidence is the weight in both numerator and denominator; abstains do not participate.

## R2 policy

The default R2 policy is an explicit first calibration hypothesis, not a market claim:

- minimum 12 cases
- 100% reviewed-case coverage
- all six set roles represented
- at least 6 decisive human judgments
- exact agreement >= 0.65
- decisive agreement >= 0.70
- confidence-weighted decisive agreement >= 0.70
- false-winner-on-human-tie rate <= 0.25

These thresholds may be revised only through a versioned governed change backed by evidence. Tests must not be weakened merely to make a model pass.

## Verdicts

R2 has exactly three verdicts:

### `INCOMPLETE`

Not enough valid evidence exists to evaluate the challenger.

### `DOES_NOT_SUPPORT_ACTIVATION`

Coverage is sufficient, but the challenger fails one or more calibration thresholds.

### `SUPPORTS_FURTHER_EVALUATION`

The bounded calibration thresholds are met. This is **not activation authorization** and is intentionally named to prevent that interpretation.

## Real R4 status

This implementation slice does not fabricate or backfill human scores. The existing qualitative track-selection observations are valuable separate DJ evidence, but they are not automatically converted into the six-dimensional Bundle 63 blinded review protocol.

Therefore the real R4 Human Preference Calibration remains incomplete until genuine full blinded reviews are ingested and corresponding Bundle 67 shadow comparisons are available for those exact cases.

## Security / privacy

R2 is pure calibration over supplied in-memory evidence:

- no audio reads
- no MIR/provider execution
- no file-system scanning
- no network calls
- no cloud upload
- no hidden telemetry
- no persistence side effects
- no optimizer mutation
- no `TransitionAssessment` mutation

## Test evidence rules

Synthetic human values may exist only in explicit test fixtures and must be marked as synthetic test data. Synthetic tests demonstrate logic; they are never product evidence and never count toward a real R4 calibration report.

## Authority

- `RELEASE_AUTHORIZATION=NO`
- `DEPLOY_AUTHORIZATION=NO`
- `PRODUCTION_ACTIVATION=NO`
- `OPTIMIZER_RANKING_ACTIVATION=NO`
- `PDM_TRAINING=NO`
- `MERGE_AUTHORIZATION=NO` until separate explicit `MERGE GO`
