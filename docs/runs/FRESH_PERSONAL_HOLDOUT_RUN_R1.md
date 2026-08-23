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
- one or more prior private review manifests carrying stable track-identity sequence evidence, including the historical real-library private manifest;
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
  --exclude-reviewer-packet "$PRIOR_REVIEW_PACKET" \
  --exclude-private-manifest "$PRIOR_PRIVATE_MANIFEST"
```

Both exclusion arguments are repeatable when more than one earlier exposure source must be covered.

The runner must fail closed before evidence generation if the checkout is not the exact canonical commit or the working tree is dirty.

## Expected private outputs

- `APPLAYLIST_FRESH_PERSONAL_HOLDOUT_R1.private.json`
- local SQLite database

The private manifest includes frozen selection, replacement/effective-cohort provenance, blind assignments, challenger evidence for the selected + fallback reservoir, and after workspace finalization an opaque stable-exposure registry for future holdout runs. Challenger evidence must be frozen before the reviewer workspace is published.

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

A case is not fresh merely because it has a new case identifier or because display metadata changed.

Before the reviewer workspace is finalized, the runner performs two independent exclusion checks:

1. reviewer-visible sequence matching against prior blinded reviewer packets;
2. stable track-ID sequence matching against prior private manifests.

It must fail closed if an effective holdout case reproduces:

- any exact previously exposed individual plan sequence; or
- any exact previously exposed A/B sequence pair.

The pre-finalization SHA-256 values of the generated private manifest, reviewer packet, and CSV are also verified before the finalizer is allowed to bind them. The reviewer case order/identity must exactly equal the frozen effective cohort, and reviewer assignment/set-role metadata must match the private frozen evidence.

Do not open Case 1 if either exposure exclusion layer or any binding check failed.

## Stop gate before Case 1

Before opening the reviewer packet, verify:

- exact canonical SHA matches the run preregistration and local HEAD;
- canonical branch is `feature/bundle-0-bootstrap`;
- working tree was clean at run start;
- selected holdout has 24 effective cases;
- all six set roles are represented with four cases each;
- reviewer case order/identity exactly matches the frozen effective cohort;
- replacement policy and effective cohort fingerprints are frozen;
- challenger comparisons for selected + fallback cases are present in private evidence and absent from reviewer-safe outputs;
- reviewer-visible and stable track-ID prior-exposure registries were both applied successfully;
- reviewer packet is bound to the frozen preregistration/selection/effective-cohort fingerprints;
- all human review and clean-attestation fields are empty at freeze;
- algorithm identity is hidden;
- transition execution is not requested.

If any check fails, do not review Case 1.
