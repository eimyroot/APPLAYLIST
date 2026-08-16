# APPLAYLIST Provider Governance v1

## Status

Proposed governance contract for MIR, ML, DSP, semantic, stem, transcription and optional cloud providers.

The purpose is to prevent technically impressive but legally, operationally or scientifically unsafe components from becoming production authority.

## Core principle

Provider accuracy is necessary but not sufficient.

Production eligibility requires simultaneous evidence for:

- quality,
- confidence behavior,
- robustness,
- reproducibility,
- runtime cost,
- privacy,
- security,
- licensing,
- model/data provenance,
- rollback.

## Provider lifecycle

```text
DISCOVERED
  -> RESEARCHED
  -> LICENSE_REVIEWED
  -> BENCHMARK_READY
  -> BENCHMARKED
  -> SECURITY_REVIEWED
  -> HUMAN_REVIEWED
  -> APPROVED
  -> PRODUCTION_ELIGIBLE
  -> ACTIVE
```

Any failed mandatory gate moves the provider to `BLOCKED` until new evidence is reviewed.

A provider can be deprecated or revoked without deleting prior analysis evidence.

## Provider record

```text
ProviderRecord
├── provider_id
├── capability
├── implementation_type
├── code_origin
├── version
├── model_id | null
├── model_version | null
├── model_hash | null
├── runtime_dependencies[]
├── license_record
├── provenance_record
├── benchmark_record
├── security_record
├── privacy_record
├── resource_profile
├── approval_state
├── approved_by
├── approved_at
└── rollback_target | null
```

## Capability taxonomy

Examples:

- tempo,
- beat,
- downbeat,
- key,
- chord,
- loudness,
- spectral,
- structure,
- vocal,
- genre/style,
- mood,
- embedding,
- stems,
- transcription,
- fingerprinting.

Approval is capability-specific.

A provider approved for tempo is not automatically approved for structure or genre.

## License gate

The license review records separately:

- source-code license,
- model-weights license,
- training-data/provenance restrictions when known,
- redistribution rights,
- commercial-use rights,
- attribution/notice obligations,
- copyleft/network-copyleft implications,
- patent or trademark constraints when relevant,
- service/API terms when remote.

States:

- `CLEAR`
- `CONDITIONAL`
- `REQUIRES_COMMERCIAL_LICENSE`
- `UNKNOWN`
- `BLOCKED`

`UNKNOWN` is not production-eligible.

## Provenance gate

Required where applicable:

- repository/source URL,
- release/tag/commit,
- model hash,
- model card or equivalent documentation,
- training-data statement if available,
- upstream maintenance state,
- reproducible installation/build steps,
- known security or integrity concerns.

A provider with opaque provenance may be benchmarked experimentally but cannot become authoritative without explicit exception evidence.

## Benchmark gate

Benchmark evidence must be capability-specific and versioned.

Required record:

```text
BenchmarkRecord
├── benchmark_id
├── capability
├── dataset_manifest_hash
├── dataset_license_state
├── source_commit
├── provider_version
├── model_hash | null
├── runtime_environment
├── metrics
├── calibration_metrics
├── failure_distribution
├── runtime_metrics
├── artifact_hashes[]
└── verdict
```

Rules:

- benchmark audio and restricted annotations remain outside the repository unless their license explicitly permits storage,
- dataset manifest/hash may be stored as evidence,
- benchmark results are immutable,
- promotion compares exact provider versions, not provider names only.

## Quality dimensions

Depending on capability, evaluate:

- absolute accuracy,
- tolerance-window accuracy,
- ambiguity handling,
- calibration/confidence quality,
- false-positive/false-negative behavior,
- genre/style distribution sensitivity,
- variable-tempo robustness,
- short/long track robustness,
- noisy/live/old-master robustness,
- failure isolation.

## Performance gate

Record:

- real-time factor,
- wall-clock duration,
- CPU utilization,
- peak memory,
- model/artifact size,
- startup cost,
- optional GPU requirement,
- batch scalability.

Performance thresholds are product-specific and versioned.

A slower provider may still be eligible as an optional `quality` mode while a faster provider serves `default` mode.

## Privacy gate

Classify provider execution:

- `LOCAL_ONLY`
- `LOCAL_WITH_OPTIONAL_NETWORK_METADATA`
- `REMOTE_AUDIO_UPLOAD`
- `REMOTE_FEATURE_UPLOAD`

Default DJ analysis should remain local-first.

Any provider that transfers audio or derived sensitive features off-device requires:

- explicit user-visible consent,
- documented destination and retention policy,
- secret handling boundary,
- network security review,
- separate product capability flag.

No hidden fallback from local analysis to remote upload is permitted.

## Security gate

Check at minimum:

- dependency risk,
- model/artifact integrity,
- arbitrary code execution surface,
- unsafe deserialization,
- network behavior,
- filesystem access scope,
- subprocess behavior,
- untrusted input handling,
- bounded resource use,
- crash/failure containment.

Providers never receive renderer authority directly.

## Human review gate

Automated metrics are not sufficient for subjective music tasks.

For semantic, structure, energy and transition-related capabilities, use a versioned human evaluation protocol containing:

- representative DJ material,
- blinded comparison where feasible,
- disagreement recording,
- failure examples,
- qualitative notes,
- acceptance/rejection threshold.

Human review evidence must not be rewritten to hide poor examples.

## Provider modes

A capability may expose several approved modes:

- `FAST`
- `BALANCED`
- `QUALITY`
- `EXPERIMENTAL`

Mode selection is explicit.

`EXPERIMENTAL` outputs cannot silently become canonical production truth.

## Consensus eligibility

Only providers with an allowed consensus state may contribute to canonical consensus.

States:

- `AUTHORITATIVE`
- `SUPPORTING`
- `EXPERIMENTAL_ONLY`
- `BLOCKED`

A supporting provider can improve disagreement detection without being allowed to overrule an authoritative measurement by itself.

## Promotion decision

A provider authority change requires a decision record containing:

- old provider/mode,
- candidate provider/mode,
- exact versions/hashes,
- benchmark comparison,
- human review summary,
- license state,
- privacy/security state,
- migration impact,
- rollback procedure,
- effective date/version.

No environment-variable-only change may silently redefine canonical music semantics.

## Rollback

Every provider promotion defines:

- previous eligible provider,
- compatibility of stored evidence,
- whether re-analysis is required,
- how affected analysis revisions are identified,
- how the renderer communicates changed authority.

Rollback never deletes the evidence produced by the revoked provider.

## ML/LLM boundary

Specialist MIR/DSP providers own measured musical facts when benchmarked for those capabilities.

An LLM may:

- explain structured facts,
- summarize comparison reasons,
- translate explanation codes,
- assist discovery/research.

An LLM must not independently become canonical authority for:

- BPM,
- beat/downbeat grid,
- key,
- loudness,
- measured spectral values,
- provider license state.

Any future multimodal model used for music semantics must pass the same provider gates as other models.

## Evidence retention

Persist:

- provider decision records,
- benchmark reports/hashes,
- license decision records,
- security/privacy decisions,
- approval/revocation history.

Do not persist restricted benchmark audio merely for convenience.

## Fail-closed rules

Production eligibility is denied when:

- license status is unknown or blocked,
- exact provider/model version is unavailable,
- benchmark evidence is missing for a required capability,
- model/artifact integrity cannot be verified where required,
- remote audio transfer is undocumented,
- rollback cannot be defined for authority replacement,
- provider emits structurally invalid normalized output.

## Required CI / evidence gates

For a production-provider change:

1. dependency/install proof,
2. normalized-contract tests,
3. deterministic fixture tests where applicable,
4. benchmark execution against approved manifest,
5. output-schema validation,
6. regression comparison against current authority,
7. license decision present,
8. security/privacy decision present,
9. artifact/evidence hashes recorded,
10. explicit authority-change approval.

## Initial implementation target

Bundle 51 may consume only capabilities already exposed through normalized analysis evidence.

Adding a new MIR/ML provider is a separate governed slice unless it is strictly required to satisfy a named Bundle 51 acceptance gate.
