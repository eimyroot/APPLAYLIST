# Bundle 42 — Bounded Library Import Boundary

## Status

Implemented on `feature/bundle-42-bounded-library-import`. Merge requires the full release gate.

## User value

A DJ can select one explicit local directory and receive deterministic evidence of supported audio candidates, skipped entries and controlled filesystem errors.

This bundle creates the discovery boundary only. It does not import metadata, analyze audio or persist records.

## Contracts

### `LibraryScanPolicy`

Immutable policy containing:

- normalized allowed extensions,
- recursive or non-recursive mode,
- hidden-entry behavior,
- symlink policy,
- maximum discovered entries,
- maximum accepted files.

Default candidate extensions:

```text
.aac .aif .aiff .flac .m4a .mp3 .ogg .opus .wav
```

An extension in this list means only that the file is a candidate for later metadata/provider validation. It is not yet a compatibility guarantee.

### `LibraryScanResult`

Immutable result containing:

- resolved absolute root,
- deterministic unique accepted paths,
- skipped evidence,
- controlled errors,
- discovered-entry count,
- cancellation state,
- entry-limit state,
- file-limit state.

### `LibraryScanIssue`

Every skipped or failed entry has a stable code, path and controlled detail.

## Scanner behavior

`LibraryScanner` uses bounded deterministic `os.scandir` traversal.

Security properties:

- relative roots are rejected before filesystem traversal,
- the root is resolved to an absolute path,
- accepted files must resolve within the selected root,
- hidden entries can be excluded,
- recursion is explicit,
- total entries and accepted files have separate limits,
- symlinks are skipped by default,
- optional allowed symlinks must resolve within the root,
- directory device/inode identity prevents loops and alias rescans,
- accepted targets are deduplicated,
- cancellation produces an explicit partial result.

## Symlink modes

### `skip`

All symlinks are evidenced and ignored.

### `allow_within_root`

A symlink may be followed only when its resolved target remains under the selected resolved root. External targets are skipped. Revisited directory identities are not traversed again.

## Isolation

This bundle does not:

- read audio tags,
- decode audio,
- import Librosa or Essentia,
- write SQLite records,
- create analysis jobs,
- expose a new API route,
- add a desktop UI,
- add a dependency.

## Verification

Required tests cover:

- policy normalization and immutable validation,
- relative/missing/non-directory roots,
- recursive and non-recursive scans,
- deterministic accepted order,
- hidden and unsupported entries,
- maximum entry and file limits,
- cancellation,
- default symlink rejection,
- allowed internal file symlink deduplication,
- external symlink rejection,
- directory-symlink loop prevention.

The full existing suite must pass on Python 3.11 and 3.12.

## Rollback

Revert the future Bundle 42 squash commit. No runtime configuration, database or generated artifact rollback is required.

## Next

Bundle 43 — Metadata and Stable Track Identity. The scanner result will become input to a separate import application service; the scanner itself must remain persistence-free.