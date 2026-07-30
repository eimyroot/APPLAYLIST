# APPLAYLIST Rhythmic and Structure Evidence v1

## Status

This document defines the canonical-reconciliation foundation for rhythmic and structural evidence on baseline `464b70cc86314a6a4abc024c9a216c863d1c9b2e`.

It ports the verified WB-006B fixture concept and adapts its contracts to the canonical `CanonicalAnalysisResult` provenance vocabulary. It does **not** activate a new BPM authority, beat-grid extractor, downbeat detector, phrase detector, structure detector, transition engine, API route, database write, or runtime path.

## Canonical authority boundary

`core.analysis.provider_contract.CanonicalAnalysisResult` remains the authority for provider identity and scalar MIR evidence. Rhythmic evidence provenance mirrors its canonical fields:

- `provider`,
- `provider_version`,
- `algorithm_version`,
- `source_analysis_version`.

`EvidenceProvenance.from_canonical_analysis(...)` fails closed when provider or algorithm version evidence is absent. It never invents provenance.

The canonical Librosa provider remains the only existing measured BPM implementation in this reconciliation slice. WB-006C is intentionally not imported or activated here.

## Scope

The evidence contract represents:

- beat timestamps with explicit beat-event confidence,
- tri-state downbeat state (`true`, `false`, `unknown`),
- independent downbeat confidence when downbeat state is known,
- bar position only when downbeat evidence is known,
- tempo confidence,
- optional meter value with independent meter confidence,
- 8-, 16-, and 32-beat phrase boundaries,
- structural segments with evidence codes,
- directional overlap windows derived from explicit phrase evidence,
- canonical provider/version/algorithm provenance,
- fail-closed unavailable results.

## Non-goals

This slice does not:

- replace `services/analysis/librosa_baseline.py`,
- replace `services/structure/structure.py`,
- import WB-006C extraction code,
- expose a new API route,
- modify database schemas,
- change canonical composition ranking,
- activate Transition Intelligence,
- activate fixed-percentage section boundaries as measured structure,
- invent confidence values,
- copy BPM confidence into downbeat or meter confidence,
- emit precise overlap beats without phrase evidence,
- add a dependency.

## Confidence rules

1. Measured or derived values carry explicit confidence in the inclusive range 0–1.
2. Unavailable evidence carries no measured values and requires an unavailable reason.
3. Beat confidence, downbeat confidence, tempo confidence and meter confidence are distinct evidence dimensions.
4. Unknown downbeat state carries no downbeat confidence or bar-position evidence.
5. Phrase confidence is not copied from tempo, onset or energy confidence without a documented calibration method.
6. Structural labels require explicit evidence codes.
7. Directional overlap windows require equal source and target beat spans and explicit provenance.

## Golden fixture policy

The WB-006B deterministic generator and manifest are preserved byte-for-byte in this reconciliation slice. The repository tracks the generator and expected SHA-256 values, not generated WAV binaries.

The fixture set contains:

- clean 120 BPM pulse tracks with 8-, 16-, and 32-beat phrase accents,
- a 64-beat structured track with deterministic section-energy changes,
- a degraded low-signal/noise variant,
- a silence negative fixture.

These fixtures prove deterministic test geometry. They do not prove real-world DJ accuracy.

## Future integration sequence

1. Land and verify this constitution + evidence/fixture foundation in isolation.
2. Extend the canonical MIR benchmark with beat-timestamp/downbeat metrics.
3. Adapt WB-006C only as a shadow benchmark candidate, not a second runtime BPM authority.
4. Compare canonical Librosa and candidate beat-grid evidence on synthetic and licensed real-world annotations.
5. Add independent downbeat, phrase and structure inference only after measured acceptance gates exist.
6. Integrate Transition Intelligence only in shadow/read-only mode through an explicit canonical evidence adapter.
7. Permit precise overlap recommendations only after phrase-evidence acceptance gates pass.
