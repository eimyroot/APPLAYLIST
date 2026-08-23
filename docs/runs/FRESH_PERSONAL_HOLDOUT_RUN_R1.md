# Fresh Personal Holdout Run R1

## Purpose

Execute a fresh personal blind curation holdout only after Bundle 70 is merged.

## Preconditions

- local APPLAYLIST checkout on the canonical commit;
- private `applaylist-local-library-snapshot-r1` JSON;
- local audio files remain readable;
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
  --blinding-seed "$BLINDING_SEED"
```

## Expected private outputs

- `APPLAYLIST_FRESH_PERSONAL_HOLDOUT_R1.private.json`
- local SQLite database

These must not be published to a public repository because the private manifest is bound to local evidence and may contain private provenance.

## Expected reviewer-safe outputs

- `APPLAYLIST_FRESH_PERSONAL_HOLDOUT_REVIEWER_R1.json`
- `APPLAYLIST_FRESH_PERSONAL_HOLDOUT_REVIEW_R1.csv`

The reviewer packet contains anonymous Plan A / Plan B sequences and only the R2 curation dimensions.

## Stop gate before Case 1

Before opening the reviewer packet, verify:

- exact canonical SHA matches the run preregistration;
- selected holdout has 24 effective cases;
- all six set roles are represented with four cases each;
- replacement policy and effective cohort fingerprints are frozen;
- challenger comparisons are present in private evidence and absent from reviewer-safe outputs;
- no human label columns contain values;
- algorithm identity is hidden;
- transition execution is not requested.

If any check fails, do not review Case 1.
