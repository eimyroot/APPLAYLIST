# Bundle 63 — Human DJ Review Execution R1

Status: governed implementation slice  
Issue: #145  
Canonical dependency: `bba282136590be91e8910aa0bc49cdd4402acc63`

## Purpose

Bundle 63 turns the already-prepared blinded real-library reviewer packet into an executable, auditable human DJ review workflow.

It does **not** fabricate human judgement.

```text
applaylist-blind-human-dj-review-packet-r1
  -> deterministic local reviewer workspace
  -> real DJ A/B judgement
  -> trusted validation
  -> append-only review ledger
  -> trusted private assignment binding
  -> canonical human-review evaluator
  -> PASS / FAIL / INCOMPLETE aggregate evidence
```

Bundle 62 explicitly names Human DJ Review execution and aggregation/governance decision as the next R4 dependency.

## Existing authority reused

Bundle 63 does not create a second musical-quality evaluator.

It reuses:

- `HUMAN_DJ_REVIEW_PROTOCOL_VERSION = human-dj-review-r1`,
- `HumanDJReview`,
- `HumanDimensionPairRating`,
- `BlindedPlanAssignment`,
- `CuratedReviewCase`,
- `HumanReviewProtocolThresholds`,
- `evaluate_curated_real_library_human_review_r1`.

A protocol `PASS` means the review evidence is complete and internally valid under the R1 thresholds. It does not mean the bounded-beam optimizer is musically superior and it does not authorize activation.

## Reviewer-visible boundary

The local reviewer workspace consumes only the blinded packet.

It exposes:

- case ID,
- set role,
- anonymous Plan A / Plan B ordered display names,
- preference: `plan_a | plan_b | tie | abstain`,
- six required paired 1–5 review dimensions:
  - transition smoothness,
  - phrase alignment,
  - energy flow,
  - dramaturgical fit,
  - set coherence,
  - alternative usefulness,
- confidence 0–1.

The workspace does not receive or expose:

- greedy/beam strategy identity,
- private plan IDs,
- private assignment mapping,
- absolute local paths,
- raw MIR payloads,
- sidecar secrets,
- optimizer activation authority,
- Personal DJ Model training authority.

The HTML is self-contained and uses no network API.

## Reviewer packet integrity

The reviewer packet fingerprint is reproduced with the exact Bundle 54 canonical algorithm.

Any mutation to reviewer-visible case material invalidates the packet fingerprint and fails closed.

Submissions must bind the exact:

- protocol version,
- packet fingerprint,
- case ID,
- assignment ID,
- reviewer reference.

A review that declares algorithm identity was visible is invalid.

## Append-only human evidence

`HumanDJReviewLedger` stores validated review evidence in SQLite.

Properties:

- append-only UPDATE/DELETE triggers,
- immutable canonical review JSON,
- one reviewer per packet/case at most once,
- exact retry idempotence,
- conflicting retry fails closed,
- deterministic review ID from the exact submitted evidence.

No synthetic or fallback review path exists.

## Trusted aggregation

Aggregation requires both:

1. the blinded reviewer packet, and
2. the private runtime evidence manifest.

The trusted evaluator verifies:

- snapshot identity,
- private evidence privacy contract,
- case identity set,
- assignment identity set,
- private case/assignment consistency.

Only then does it load append-only human evidence and call the existing canonical human-review evaluator.

Private slot-to-strategy mapping is never copied into the reviewer workspace.

## Aggregate outcome

The output schema is:

`applaylist-human-dj-review-aggregate-r1`

It contains the canonical `CuratedRealLibraryHumanReviewReport` plus explicit authority-false flags.

Possible protocol verdicts remain:

- `PASS`
- `FAIL`
- `INCOMPLETE`

No review count, preference count, dimension score or PASS verdict can independently authorize optimizer/ranking activation.

## CLI

```bash
python scripts/applaylist_human_dj_review.py workspace \
  --packet APPLAYLIST_BLINDED_HUMAN_DJ_REVIEW_PACKET_R1.json \
  --output APPLAYLIST_HUMAN_DJ_REVIEW_WORKSPACE_R1.html

python scripts/applaylist_human_dj_review.py ingest \
  --packet APPLAYLIST_BLINDED_HUMAN_DJ_REVIEW_PACKET_R1.json \
  --submission reviewer-01.json \
  --ledger APPLAYLIST_HUMAN_DJ_REVIEW_R1.sqlite \
  --receipt reviewer-01.receipt.json

python scripts/applaylist_human_dj_review.py report \
  --packet APPLAYLIST_BLINDED_HUMAN_DJ_REVIEW_PACKET_R1.json \
  --private-manifest APPLAYLIST_REAL_LIBRARY_RUNTIME_EVIDENCE_R1.private.json \
  --ledger APPLAYLIST_HUMAN_DJ_REVIEW_R1.sqlite \
  --output APPLAYLIST_HUMAN_DJ_REVIEW_AGGREGATE_R1.json
```

The private runtime manifest remains private evidence and must not be distributed to reviewers.

## Fail-closed examples

- packet fingerprint mismatch,
- unsupported packet/submission schema,
- algorithm identity visible,
- missing one of the six dimensions,
- score outside 1–5,
- confidence outside 0–1,
- case/assignment mismatch,
- stale packet fingerprint,
- duplicate conflicting reviewer/case submission,
- private snapshot mismatch,
- private case/assignment mismatch,
- authority escalation flag.

## Explicit non-scope

- generating human judgements,
- interpreting protocol PASS as musical superiority,
- optimizer/ranking activation,
- Personal DJ Model training,
- production activation,
- cloud review service,
- release/deploy/signing/notarization.

## Next dependency

After Bundle 63 is merged and real human DJ evidence has actually been collected, the next governed boundary is the **R4 pilot evidence / governance decision**: interpret measured preference, workflow-use and trust evidence and decide whether to continue, adjust ranking, or stop/pivot.

That later decision cannot be inferred from test fixtures or from protocol completeness alone.
