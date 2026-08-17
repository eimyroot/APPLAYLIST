# APPLAYLIST Bundle 55B — Real-Library Incremental Evidence Reconciliation R1

## Status

Implementation slice only. No merge, release, deploy, production activation, optimizer activation, or Personal DJ Model training is authorized by this document.

## Purpose

Bundle 54 proved a real local-audio path, but its benchmark bridge directly hashes and analyzes every selected track before case materialization. Bundle 55 established exact reuse for canonical Bundle 50 AnalysisEvidence. Bundle 55B reconnects the real-library bridge to that canonical evidence path.

The performance goal is architectural work elimination, not a larger worker count.

## Runtime split

```text
REAL AUDIO
   |
   v
ContentTrackIdentityService
actual bytes -> aptrack:v1:sha256:<digest>
   |
   v
PERSISTENT PRIVATE ANALYSIS DB
Bundle 50 AnalysisJob + AnalysisEvidence
   |
   | exact hit --------------------> reuse evidence_id, 0 MIR calls
   |
   | miss / identity drift --------> canonical provider -> append evidence
   v
MusicDNARevision
   |
   v
Bundle 54 case materialization
TransitionAssessment -> greedy/beam -> blinded review packet
```

The per-run TransitionAssessment/optimizer database remains isolated from the persistent analysis evidence database.

## Stable analysis database

The CLI accepts `--analysis-database`. When omitted, it derives a stable private database beside the run directories:

```text
real-library-pilot-r1/
├── APPLAYLIST_REAL_LIBRARY_ANALYSIS_EVIDENCE_R1.sqlite3
├── <run-a>/
└── <run-b>/
```

This preserves compatibility with the existing launcher while making analysis evidence durable across subsequent runs.

## Exact reuse authority

Reuse is delegated to Bundle 55. A track is eligible only when:

- actual bytes produce canonical `aptrack:v1:sha256:<digest>` identity,
- successful persisted AnalysisEvidence exists,
- provider matches,
- canonical analysis version matches,
- provider version matches,
- algorithm version matches.

Anything uncertain executes the provider again.

## Content identity cost

Warm runs still verify actual file bytes through `ContentTrackIdentityService`. This is intentional. The opaque inventory `File Signature`, path, filename, size, or mtime alone are not promoted to cryptographic content authority.

The eliminated work is the expensive full MIR provider execution (decode, HPSS, beat/onset, chroma/CQT, RMS/spectral analysis), not the bounded streaming SHA-256 identity proof.

## Interruption / restart

Reconciliation creates one persisted AnalysisJob work unit per selected content identity. Successful evidence is appended before moving to the next selected track. A restarted run therefore re-hashes identity but reuses already completed exact analysis evidence and executes MIR only for incomplete or invalidated content.

## Progress evidence

The CLI emits bounded path-free progress events:

```text
MIR_PROGRESS {
  "stage": "analysis_evidence_reused",
  "targets_total": 124,
  "evidence_reused": 83,
  "provider_executed": 2,
  "succeeded": 85,
  "failed": 0,
  "remaining": 39
}
```

No absolute local path is emitted by progress telemetry.

## Acceptance matrix

| Scenario | Expected provider execution |
| --- | --- |
| cold analysis DB | all selected content |
| warm exact identity | 0 |
| one track byte change | changed content only |
| provider/algorithm/version drift | invalidated content only |
| interruption + restart | unfinished/invalidated content only |
| legacy/non-content identity | no reuse |
| provider drift + fresh failure | fail closed; never use stale success |

A reuse hit must not append duplicate successful AnalysisEvidence.

## Current Bundle 54 pilot migration boundary

The already-running Bundle 54 cold pilot predates Bundle 55B and does not persist its full canonical MIR result into the new persistent AnalysisEvidence database. Its private runtime manifest is intentionally not auto-imported because it does not contain every canonical analysis field required to prove exact semantic equivalence.

Therefore R1 does **not** synthesize or reconstruct missing canonical fields from the old private manifest. The current cold pilot remains valid evidence; future Bundle 55B runs establish the durable reusable evidence base without falsifying provenance.

## Truth and authority boundaries

Bundle 55B does not:

- reinterpret inventory `File Signature` as SHA-256,
- create a second cache authority,
- create a second track identity,
- change MusicDNA or TransitionAssessment scoring semantics,
- change `TransitionAssessment` as sole pairwise transition authority,
- expose local paths in reviewer-visible output,
- alter blind PLAN_A / PLAN_B semantics,
- activate optimizer ranking in production,
- train a Personal DJ Model,
- upload the user's audio library to cloud services.

## Review evidence

Private runtime evidence adds the canonical `analysis_evidence_id` and reconciliation counters. Reviewer-visible packets remain algorithm-blinded and path-free.

## Governed next gate

Required before merge:

- exact-head CI Python 3.11 PASS,
- exact-head CI Python 3.12 PASS,
- regression suite PASS,
- PR Guard PASS,
- zero unresolved review threads,
- explicit merge authorization.

`MERGE_AUTHORIZATION=NO`
`RELEASE_AUTHORIZATION=NO`
`DEPLOY_AUTHORIZATION=NO`
`PRODUCTION_EFFECTS=NO`
