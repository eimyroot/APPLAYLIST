# APPLAYLIST MIR Benchmark Specification v1

## Status

Accepted benchmark design. No provider is approved as the production default by this document.

## Purpose

APPLAYLIST must choose audio providers using measured DJ-relevant quality, performance, licensing and packaging evidence.

A green unit-test suite proves software behavior. It does not prove BPM, key or energy accuracy.

## Benchmark questions

1. Can the provider decode the supported local library reliably?
2. Is BPM accurate after accounting for half/double-tempo ambiguity?
3. Is key useful for Camelot-oriented DJ transitions?
4. Does the energy value preserve a useful ranking for set construction?
5. Is analysis fast enough for a local desktop workflow?
6. Does the provider package and license fit the intended commercial distribution?

## Providers under evaluation

### Baseline candidate

Librosa with NumPy/SciPy/SoundFile behind a lazy provider boundary.

Required remediation before benchmarking:

- no module-level optional import on mandatory boot,
- no repository write inside provider code,
- normalized raw result contract,
- provider and algorithm version evidence,
- confidence/warning fields,
- controlled decode/runtime/output failures.

### Advanced candidate

Essentia may be evaluated as an optional benchmark provider. It is not approved for commercial distribution until licensing is resolved.

### Excluded from initial decision

- providers returning stub or empty musical descriptors,
- remote services requiring upload of user audio,
- models with unresolved non-commercial restrictions,
- algorithms that cannot report version/provenance.

## Datasets

The benchmark must include both public reference data and a private legal DJ evaluation collection.

### Public reference categories

- electronic-dance tempo annotations,
- electronic-dance key annotations,
- beat/downbeat data where licensing permits local evaluation.

Dataset manifests must record:

- name and version,
- source URL,
- license,
- checksum,
- permitted use,
- local storage location outside the repository.

Audio files and restricted datasets must not be committed.

### Private DJ evaluation set

Minimum initial target: 200 legally controlled tracks, stratified across:

- house,
- tech house,
- groove techno,
- hypnotic techno,
- tracks with beatless intros/outros,
- live or unstable percussion,
- half/double-tempo ambiguity,
- major/minor and modal ambiguity,
- long breakdowns and dynamic energy changes.

Each reference item should contain manual evidence for BPM and key and a DJ energy score. Annotation provenance must identify the human and method.

## Ground-truth representation

### BPM

Store:

- reference BPM,
- accepted alternate half/double value where musically equivalent,
- confidence/annotation notes.

### Key

Store tonic and mode plus normalized Camelot value where applicable.

Evaluation categories:

- exact tonic/mode,
- relative major/minor,
- adjacent Camelot position,
- compatible but non-exact,
- incompatible.

### Energy

Energy is not treated as a universal physical truth. Store a DJ-oriented ordinal score and optional pairwise ranking annotations.

## Metrics

### Decode reliability

- supported files attempted,
- successful analyses,
- controlled failures,
- uncontrolled exceptions,
- median and p95 duration.

### BPM

- exact within +/- 1%,
- correct after half/double normalization,
- absolute percentage error,
- catastrophic outlier count.

### Key

- exact accuracy,
- relative accuracy,
- Camelot-compatible accuracy,
- incompatible error rate.

### Energy

- Spearman rank correlation,
- pairwise ordering agreement,
- distribution collapse detection,
- genre-stratified performance.

### Runtime

Measure on the supported development Mac and at least one representative target machine:

- real-time factor,
- median and p95 seconds per track,
- peak memory,
- cold-start cost,
- concurrency behavior.

### Data integrity

- NaN/inf count,
- missing required descriptor count,
- invalid Camelot/key count,
- persistence validation failures.

## Proposed acceptance gates

These are APPLAYLIST product gates, not universal industry standards.

| Metric | Initial gate |
|---|---:|
| Supported-file decode success | >= 99.5% |
| Controlled rather than uncontrolled failure | 100% |
| Duration availability | >= 99.9% |
| BPM correct after half/double normalization | >= 95% within +/- 1% |
| Exact key accuracy | >= 75% |
| Camelot-compatible key accuracy | >= 90% |
| Invalid numeric values persisted | 0 |
| Exported paths existing | 100% |
| Determinism for fixed input/version | 100% |
| Energy rank correlation on private set | >= 0.75 |
| DJ-rated playable transitions | >= 85% |

A threshold may be changed only with a documented rationale and versioned benchmark report.

## Human transition evaluation

Automatic descriptor metrics are necessary but insufficient.

A blind evaluation should sample generated adjacent pairs and ask DJs to classify:

- playable,
- playable with manual correction,
- not playable.

Record reasons:

- BPM jump,
- harmonic clash,
- energy mismatch,
- phrasing/structure issue,
- artist/label repetition,
- subjective preference.

The benchmark report must separate objective rule violations from subjective rejection.

## Reproducibility

Each run produces a machine-readable report containing:

- benchmark schema version,
- dataset manifest checksums,
- provider and dependency versions,
- source commit,
- hardware/OS/Python information,
- configuration,
- per-track outputs and errors,
- aggregate metrics.

Generated reports belong under ignored artifacts storage unless a redacted aggregate report is intentionally committed.

## Decision matrix

Provider selection weighs:

| Dimension | Weight |
|---|---:|
| BPM/key quality | 35% |
| Decode reliability | 20% |
| Energy usefulness | 15% |
| Runtime/packaging | 15% |
| License/commercial suitability | 15% |

A provider that fails licensing or controlled-failure requirements cannot win through accuracy alone.

## Decision gate

The production default cannot change until:

- the baseline provider is benchmarked,
- the advanced candidate is benchmarked if legally available,
- results are reviewed by a human DJ,
- persistence compatibility is proven,
- rollback to the prior provider is verified,
- the license register marks the selected stack as approved.

## Required implementation bundle

The benchmark harness is scheduled after real baseline-provider hardening and before desktop UI composition becomes release-authoritative.