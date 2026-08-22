# Bundle 66 — Historical Meaningful Review Replay R1

## Purpose

Operationalize Bundle 65 against the existing R4/R2 real-library evidence without re-reading or re-analyzing audio.

Invariant:

`HISTORICAL_EVIDENCE_REPLAY != REANALYSIS`

The existing R2 snapshot, curated selection, private runtime manifest, optimizer plan identities, and canonical provider-derived energy are treated as immutable source evidence. Snapshot genre metadata is reused as style evidence. No historical artifact is rewritten.

## Why this slice exists

Bundle 65's first real-library wrapper intentionally reuses the original materializer path. That path calls `analyze_real_tracks(...)`, which hashes and decodes selected audio and invokes the MIR provider. R4 already has complete R2 evidence, so repeating MIR solely to evaluate the new post-search gate would create unnecessary provenance drift.

Bundle 66 adds a narrow replay adapter rather than weakening Bundle 65 or silently regenerating evidence.

## Inputs

Private/local evidence only:

- `applaylist-local-library-snapshot-r1`
- `applaylist-curated-case-selection-r1`
- `applaylist-private-runtime-music-evidence-r1`

The replay validates:

- snapshot schema and privacy contract;
- selection snapshot binding;
- private-manifest snapshot binding;
- exact case-id set equality;
- case snapshot/set-role/seed binding;
- greedy and beam strategy identity;
- plan/result/path ids;
- blind-assignment integrity;
- private track duration/energy bounds;
- all path track references.

## Evaluation view

Historical `ReviewableSetPlan` data contains the source ordered track ids, transition ids, result id, and path id. Bundle 66 reconstructs a bounded in-memory `SetPathAlternative` **view** solely so the existing Bundle 65 coherence/diversity evaluator can consume the historical path.

The replay view:

- preserves source result/path/plan ids in the output report;
- treats each historical best plan as source rank 1;
- does not publish synthetic candidate scores as source optimizer truth;
- does not call Set Intelligence search;
- does not write TransitionAssessment evidence;
- does not mutate optimizer ranking.

## Evidence mapping

- style: snapshot `genre` -> Bundle 65 `TrackMusicalEvidence.style_tags`;
- energy: private runtime manifest canonical `energy`;
- duration: private runtime manifest canonical `duration_seconds` for contract-safe in-memory path state;
- analysis provenance: private `analysis_revision`.

Missing style or energy remains fail-closed and produces `not_proven_missing_evidence` through the existing Bundle 65 policy.

## Output

One new immutable JSON report:

`APPLAYLIST_HISTORICAL_MEANINGFUL_REPLAY_R1.json`

The output records source input SHA-256 hashes, Bundle 65 policy, per-case coherence/comparison results, failed case ids, and explicit negative authority flags.

The replay never regenerates a blinded reviewer packet and never changes R1/R2 source artifacts.

## Security / privacy

- zero audio file reads;
- zero MIR/provider calls;
- zero network calls;
- zero cloud upload;
- input JSON symlinks rejected;
- existing output or dangling output symlink rejected;
- private absolute audio paths may exist in the private manifest but are never opened or copied into the replay report;
- no release/deploy/production/optimizer/PDM authority.

## CLI

```bash
python scripts/applaylist_historical_meaningful_replay.py \
  --snapshot /private/path/APPLAYLIST_LOCAL_LIBRARY_SNAPSHOT_R1.json \
  --selection /private/path/APPLAYLIST_CURATED_CASE_SELECTION_R2.json \
  --private-manifest /private/path/APPLAYLIST_REAL_LIBRARY_RUNTIME_EVIDENCE_R2.private.json \
  --output /private/new-evidence/APPLAYLIST_HISTORICAL_MEANINGFUL_REPLAY_R1.json \
  --generated-at 2026-08-22T00:00:00Z
```

The exact historical filenames are environment evidence, not assumed by the implementation. The user must point the CLI at the authoritative local files.

## Acceptance

- full supported-Python CI green;
- PR Guard green;
- deterministic replay test green;
- near-equivalent paths produce insufficient meaningful diversity;
- meaningful coherent pair can pass;
- missing style/energy is fail-closed;
- cross-artifact tampering is rejected;
- nonexistent audio paths do not prevent replay;
- overwrite/dangling-symlink output is rejected;
- review threads 0 before merge authorization.

## Authority

- `RELEASE_AUTHORIZATION=NO`
- `DEPLOY_AUTHORIZATION=NO`
- `PRODUCTION_ACTIVATION=NO`
- `OPTIMIZER_RANKING_ACTIVATION=NO`
- `PDM_TRAINING=NO`
- `MERGE_AUTHORIZATION=NO` until separate explicit `MERGE GO`
