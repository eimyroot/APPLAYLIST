# Bundle 26 — Export Path Integrity and Unique Pipeline Runs

## Goal

Ensure that every track selected by the composer carries a resolvable source path and that every pipeline invocation writes isolated export artifacts.

## Confirmed defect

The previous composer loaded rows directly from `analyses`. The source audio path is stored in `tracks`, so the exporter received `AnalysisRecord` instances without a `path` attribute. CI evidence showed composed tracks with `resolved_count=0` and all entries skipped as `missing_path`.

The pipeline also used the constant identifier `pipeline_run`, allowing repeated or concurrent invocations to overwrite the same M3U, manifest, warning and audit files.

## Implementation

- add immutable `PlaylistCandidate` read model
- add repository query joining `analyses` and `tracks` by `track_id`
- include only rows with a non-empty track path
- remove direct SQLite access from `Composer`
- inject composer/exporter dependencies for deterministic tests
- allow explicit export/artifact directories in `Exporter`
- generate `pipeline-<uuid>` for every pipeline invocation
- preserve the existing public response shape and database schema

## Fail-closed behavior

An analysis without a matching track row is not a playlist candidate and cannot reach the exporter. No fallback invents or copies a path into the analysis table.

## Verification contract

- existing test suite remains green
- joined tracks produce resolved M3U entries
- orphan analyses are excluded
- `resolved_count` equals composed `count` for valid candidates
- consecutive pipeline runs produce distinct playlist IDs and artifact paths
- Python 3.11 and 3.12 CI must pass before merge

## Rollback

Revert the future Bundle 26 squash commit. No schema or data migration rollback is required.
