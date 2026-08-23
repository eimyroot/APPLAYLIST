# Fresh Personal Holdout Run R1

## Purpose

Execute a fresh personal blind curation holdout only after Bundle 70 is merged.

## Preconditions

- local APPLAYLIST checkout on canonical branch `feature/bundle-0-bootstrap`;
- local HEAD exactly matches the canonical SHA supplied to the runner;
- local working tree is clean;
- private `applaylist-local-library-snapshot-r1` JSON;
- local audio files remain readable;
- one or more prior blinded reviewer packets covering sequences already exposed to the reviewer, including the historical 12-case packet;
- no reviewer labels have been collected for the new run;
- sampling and blinding seeds are chosen before review.

## Local command

```bash
python scripts/applaylist_fresh_personal_holdout.py \
  --snapshot "$SNAPSHOT" \
  --output "$OUTPUT" \
  --database "$OUTPUT/APPLAYLIST_FRESH_PERSONAL_HOLDOUT_R1.sqlite" \
  --canonical-sha "$CANONICAL_SHA" \
  --generated-at "$GENERATED_AT" \
  --sampling-seed "$SAMPLING_SEED" \
  --blinding-seed "$BLINDING_SEED" \
  --prior-review-packet "$PRIOR_REVIEW_PACKET"
```

The runner must fail closed before evidence generation if the checkout is not the exact canonical commit or the working tree is dirty.

## Expected private outputs

- `APPLAYLIST_FRESH_PERSONAL_HOLDOUT_R1.private.json`
- local SQLite database

The private manifest includes frozen selection, replacement/effective-cohort provenance, blind assignments, and challenger evidence for the selected + fallback reservoir. Challenger evidence must be frozen before the reviewer workspace is published.

These outputs must not be published to a public repository because the private manifest is bound to local evidence and may contain private provenance.

## Expected reviewer-safe outputs

- `APPLAYLIST_FRESH_PERSONAL_HOLDOUT_REVIEWER_R1.json`
- `APPLAYLIST_FRESH_PERSONAL_HOLDOUT_REVIEW_R1.csv`

The reviewer packet contains anonymous Plan A / Plan B sequences and only the R2 curation dimensions:

- `energy_flow`
- `dramaturgical_fit`
- `set_coherence`
- `alternative_usefulness`

The CSV contains system binding fields and explicit R2 clean-attestation columns, but all human-controlled fields must be empty when the workspace is frozen.

## Prior-exposure exclusion

A case is not fresh merely because it has a new case identifier.

Before the reviewer workspace is finalized, the runner must compare every effective Plan A / Plan B sequence against the supplied prior blinded reviewer packet(s). It must fail closed if an effective holdout case reproduces:

- any exact previously exposed individual plan sequence; or
- any exact previously exposed A/B sequence pair.

Do not open Case 1 if prior-exposure exclusion was not performed successfully.

## Stop gate before Case 1

Before opening the reviewer packet, verify:

- exact canonical SHA matches the run preregistration and local HEAD;
- canonical branch is `feature/bundle-0-bootstrap`;
- working tree was clean at run start;
- selected holdout has 24 effective cases;
- all six set roles are represented with four cases each;
- replacement policy and effective cohort fingerprints are frozen;
- challenger comparisons for selected + fallback cases are present in private evidence and absent from reviewer-safe outputs;
- prior-exposure registry was applied and no effective plan duplicates an exposed sequence;
- reviewer packet is bound to the frozen preregistration/selection/effective-cohort fingerprints;
- all human review and clean-attestation fields are empty at freeze;
- algorithm identity is hidden;
- transition execution is not requested.

If any check fails, do not review Case 1.
