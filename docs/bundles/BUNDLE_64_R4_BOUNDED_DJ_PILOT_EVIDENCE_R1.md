# Bundle 64 — R4 Bounded DJ Pilot Evidence R1

Status: governed implementation slice  
Issue: #148  
Canonical dependency: `8474d6c0c526e714c6b0a4fece5b47f0be5ade32`

## Purpose

Bundle 64 implements the evidence boundary required by the R4 go-to-market checkpoint.

It does not add another editor feature and it does not turn APPLAYLIST into an analytics product.

```text
real local DJ pilot use
  -> explicit bounded workflow events
  -> explicit exit survey evidence
  -> strict validation + correlation
  -> append-only local SQLite ledger
  -> deterministic product metrics
  + optional canonical Bundle 63 Human DJ Review aggregate
  -> INCOMPLETE / READY_FOR_HUMAN_DECISION
```

No synthetic usage or survey evidence is generated.

## Why this slice exists

The R4 roadmap requires a bounded DJ pilot before feature scope broadens. The named questions are no longer primarily engineering questions:

- does APPLAYLIST reduce preparation time,
- do DJs inspect and act on its recommendations,
- how much manual correction remains necessary,
- do DJs successfully export a usable result,
- do they return in a later week,
- do they trust and understand the system,
- would they pay for it,
- and does the blinded Human DJ Review evidence from Bundle 63 support continuing the current intelligence direction.

A CI pass cannot answer those questions. Bundle 64 therefore creates a governed evidence mechanism for real pilot use.

## Local-first boundary

All R1 evidence is written to an explicitly supplied local SQLite file.

There is:

- no analytics SDK,
- no HTTP client,
- no SaaS collector,
- no cloud upload path,
- no background telemetry,
- no tracking outside an explicitly bounded pilot.

Every event, survey, receipt and report carries authority-false fields. The code has no path that converts pilot evidence into optimizer activation, production activation or Personal DJ Model training.

## Workflow event contract

Schema:

`applaylist-r4-pilot-event-r1`

Protocol:

`r4-bounded-dj-pilot-r1`

Required event vocabulary:

- `import_started`
- `usable_set_reached`
- `recommendation_presented`
- `recommendation_inspected`
- `recommendation_accepted`
- `recommendation_rejected`
- `manual_reorder`
- `manual_replace`
- `manual_lock`
- `export_completed`

Each event is bound to:

- `participant_ref`
- `session_id`
- `event_ref`
- `event_type`
- timezone-aware `observed_at`
- optional bounded `object_ref`
- optional bounded scalar `metadata`

Recommendation events require `object_ref` so the denominator and subsequent interaction refer to one explicit recommendation presentation.

## Correlation rules

The ledger fails closed when:

- `usable_set_reached` has no prior `import_started` in that participant/session,
- usable-set time precedes import time,
- recommendation inspection has no matching prior presentation,
- recommendation decision has no matching prior inspection,
- the same recommendation presentation is inspected twice,
- both accept and reject are attempted for one immutable recommendation presentation,
- a singleton import/usable-set event is duplicated under another event reference.

Exact retries with the same natural key and identical canonical bytes are idempotent. A changed retry under the same natural key is rejected.

## Exit survey contract

Schema:

`applaylist-r4-pilot-survey-r1`

The survey is explicit human evidence. It contains:

- participant reference,
- survey reference,
- timezone-aware observation time,
- willingness-to-pay: `yes | no | unsure`,
- optional stated monthly price in integer minor units,
- explicit three-letter uppercase currency token when a price exists,
- trust score 1–5,
- explainability score 1–5,
- optional bounded note and reason codes.

Currency values are never converted implicitly. Price evidence remains separated by currency in the report.

## Append-only evidence

`PilotEvidenceLedger` creates two SQLite tables:

- `pilot_events`
- `pilot_surveys`

Both tables have `UPDATE` and `DELETE` denial triggers.

Identity is deterministic from canonical validated evidence. Exact retries do not create a second evidence row. Conflicting retries fail closed.

## Product metrics

The deterministic R1 report exposes:

### Preparation

- import-session count,
- count of import -> usable-set samples,
- mean preparation seconds,
- median preparation seconds.

### Recommendation workflow

- presented count,
- inspected count,
- inspection rate,
- accepted count,
- rejected count,
- acceptance/rejection rates.

`recommendation_presented` is explicit because an inspection percentage requires a real denominator.

### Human editor activity

Per import session:

- reorder count/rate,
- replace count/rate,
- lock count/rate.

Zero manual edits are a measurable result when an import session exists; the system does not require an edit merely to mark the metric assessable.

### Export

- import-session count,
- sessions with a completed export,
- export completion rate.

### Repeat weekly use

Repeat use is not marked assessable until actual workflow evidence spans at least two ISO weeks.

The report then exposes:

- number of ISO weeks represented,
- participants with workflow evidence,
- participants active in at least two distinct ISO weeks,
- repeat-use rate.

### Commercial/trust evidence

- willingness-to-pay yes/no/unsure counts and yes-rate,
- stated monthly-price medians kept separate per currency,
- mean trust score,
- mean explainability score.

## Bundle 63 binding

`build_r4_pilot_report` may receive the canonical:

`applaylist-human-dj-review-aggregate-r1`

The aggregate fingerprint is recomputed and validated. Activation/PDM/musical-superiority authority must remain false.

Its `pass | fail | incomplete` verdict is preserved as an evidence input only.

A Bundle 63 `PASS` still means protocol completeness/integrity, not automatic musical superiority.

## Evidence state

Bundle 64 has only two evidence states:

- `INCOMPLETE`
- `READY_FOR_HUMAN_DECISION`

`READY_FOR_HUMAN_DECISION` requires:

1. all named R4 product metric categories to be assessable, and
2. the bound Bundle 63 Human DJ Review aggregate to be complete (`pass` or `fail`, not `incomplete`).

Even then:

```text
product_decision=UNDECIDED
optimizer_ranking_activation_authorized=false
personal_dj_model_training_authorized=false
production_activation_authorized=false
musical_superiority_implied=false
```

A human governed decision remains a separate later action.

## CLI

Record one validated real workflow event:

```bash
python scripts/applaylist_r4_pilot.py event \
  --ledger APPLAYLIST_R4_PILOT_EVIDENCE_R1.sqlite \
  --input event.json \
  --receipt event.receipt.json
```

Record one explicit survey:

```bash
python scripts/applaylist_r4_pilot.py survey \
  --ledger APPLAYLIST_R4_PILOT_EVIDENCE_R1.sqlite \
  --input survey.json \
  --receipt survey.receipt.json
```

Build a report and bind Bundle 63 human-review evidence:

```bash
python scripts/applaylist_r4_pilot.py report \
  --ledger APPLAYLIST_R4_PILOT_EVIDENCE_R1.sqlite \
  --human-review-aggregate APPLAYLIST_HUMAN_DJ_REVIEW_AGGREGATE_R1.json \
  --output APPLAYLIST_R4_PILOT_REPORT_R1.json
```

The CLI only reads/writes explicit local files and refuses to overwrite output evidence files.

## Test-fixture rule

Tests use synthetic event/survey values solely to prove validation, correlation, immutability and deterministic metric semantics.

They are not pilot evidence and must never be presented as product validation.

## Explicit non-scope

- automatic product GO/NO-GO,
- automatic optimizer/ranking activation,
- Personal DJ Model training,
- production activation,
- cloud analytics,
- broad telemetry,
- new recommendation/editor functionality,
- new MIR/provider capability,
- release/deploy/signing/notarization.

## Next dependency

After this slice is merged, the next step is operational rather than speculative engineering:

1. run the bounded pilot with real DJs,
2. collect genuine Bundle 63 blinded review evidence,
3. collect genuine Bundle 64 workflow/survey evidence,
4. generate the immutable aggregate report,
5. make a separate governed human `CONTINUE / ADJUST / STOP-PIVOT` decision.

No such product decision is inferred from CI or test fixtures.
