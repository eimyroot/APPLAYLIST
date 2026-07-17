# APPLAYLIST License Decision Register v1

## Status

Initial compliance register. Entries marked `review_required` are not approved for product distribution.

This document is an engineering control, not legal advice. Final commercial distribution decisions require legal review appropriate to the business model and target jurisdictions.

## Decision states

- `approved_dev` — permitted for development and CI under current understanding.
- `approved_distribution` — cleared for intended packaged distribution with documented obligations.
- `experiment_only` — may be used for isolated evaluation but not shipped.
- `review_required` — unresolved; do not add to product dependencies or installers.
- `rejected` — must not be used for the stated product mode.

## Current runtime stack

| Component | Intended role | Current state | Required action |
|---|---|---|---|
| Python | runtime | approved_dev | verify redistribution notices for packaged app |
| FastAPI | local/headless API | approved_dev | include dependency license manifest |
| Pydantic | contracts/configuration | approved_dev | include dependency license manifest |
| NumPy | numerical baseline | approved_dev | verify binary-wheel notices in packaged app |
| SciPy | signal-processing baseline | approved_dev | verify binary-wheel notices in packaged app |
| SoundFile | audio decode boundary | approved_dev | audit bundled native `libsndfile` obligations |
| Librosa | baseline MIR candidate | approved_dev | benchmark; move behind lazy provider boundary |
| TinyTag 2.2.1 | read-only audio metadata | approved_dev | retain MIT notice; verify exact resolved version and packaged SBOM before distribution |

`approved_dev` does not automatically mean approved for a signed commercial installer.

## Candidate metadata dependencies

| Component | Candidate use | State | Decision notes |
|---|---|---|---|
| TinyTag 2.2.1 | read-only audio metadata | approved_dev | MIT, pure Python, no dependencies, read-only API; supports MP3/MP2/MP1, M4A/AAC/ALAC, WAV, OGG/Opus/Vorbis, FLAC, WMA and AIFF families |
| Mutagen | metadata read/write | review_required | broader functionality than MVP needs; do not add while read-only TinyTag satisfies the accepted scope |

Product preference is the smallest read-only metadata dependency that satisfies supported formats and can be safely packaged.

## Candidate MIR dependencies

| Component | Candidate use | State | Decision notes |
|---|---|---|---|
| Essentia | advanced BPM/key/energy benchmark | experiment_only | commercial distribution requires explicit licensing decision; model licenses must be evaluated individually |
| Essentia pretrained models | optional ML descriptors | review_required | no model may be downloaded or shipped without per-model license record |
| madmom | beat/downbeat research | review_required | release age, compatibility and model-data restrictions require review; not an MVP dependency |
| remote audio-analysis API | analysis provider | rejected for MVP | conflicts with local-first privacy and reproducibility goals unless separately approved |

## Desktop candidates

| Component | Candidate use | State | Decision notes |
|---|---|---|---|
| PySide6 / Qt for Python | desktop shell | review_required | available under community LGPLv3/GPLv3 or commercial Qt terms; packaging approach and compliance plan required |
| Qt commercial distribution | desktop shell | review_required | evaluate cost and licensing against business model before dependency approval |
| pyside6-deploy / Nuitka path | packaging | review_required | run reproducible macOS and Windows packaging proof; audit transitive licenses and generated notices |

No desktop dependency may be added to the main runtime dependency set before the desktop licensing gate.

## Export formats and interoperability

| Format/integration | State | Notes |
|---|---|---|
| M3U8 | approved_dev | first MVP export; path-integrity and encoding tests required |
| JSON manifest | approved_dev | internal evidence format; schema version required |
| rekordbox XML | review_required | implement from documented import format; avoid proprietary database manipulation |
| Traktor NML | review_required | format and compatibility tests required before product claim |
| OneLibrary | monitor | evaluate only through published compatible interfaces or partnership path |
| proprietary database reverse engineering | rejected | outside MVP and unacceptable without explicit legal/product approval |

## Datasets

Every benchmark dataset requires a manifest containing:

- dataset name/version,
- source and retrieval date,
- license text or stable reference,
- allowed research/commercial use,
- redistribution permission,
- checksums,
- storage location.

Rules:

- dataset audio is never committed to the repository,
- non-redistributable annotations stay outside source control,
- public reports contain only permitted aggregate or derived data,
- private DJ collections require documented ownership or permission.

## Installer compliance requirements

Before any external release:

1. generate a complete SBOM from the resolved packaged environment,
2. collect dependency and native-library license notices,
3. document source-offer or relinking obligations where applicable,
4. verify that no `experiment_only` or `review_required` component is packaged,
5. verify code signing and notarization inputs contain no secrets,
6. archive the exact dependency lock and build provenance,
7. run the packaged application on a clean target machine.

## Approval template

A dependency may move to `approved_distribution` only with a decision record containing:

- exact package and version,
- role and alternatives considered,
- upstream license and copyright notices,
- transitive/native dependencies,
- dynamic/static linking and packaging method,
- distribution obligations,
- security maintenance status,
- approving reviewer and date.

## Immediate decisions

- use TinyTag only for read-only tagged metadata ingestion,
- retain filename fallback as explicit degraded evidence rather than silent success,
- use Librosa only as a baseline benchmark candidate until quality gates pass,
- keep Essentia out of production dependencies,
- do not start the desktop implementation before a desktop licensing and packaging decision,
- implement M3U8 before proprietary ecosystem adapters,
- prohibit unreviewed pretrained-model downloads in runtime or CI.
