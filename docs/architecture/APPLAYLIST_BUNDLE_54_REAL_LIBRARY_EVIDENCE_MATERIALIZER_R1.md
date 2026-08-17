# APPLAYLIST Bundle 54 — Real-Library Evidence Materializer R1

## Purpose

Bundle 54 closes the runtime evidence gap between the canonical Human DJ Review Protocol R1 and a real blind pilot. It does **not** commit private library data and does **not** claim the pilot has run.

The local-only materializer consumes two private CASER inputs:

1. `LOCAL_LIBRARY_SNAPSHOT_R1` with exact local paths and inventory signatures,
2. `CURATED_CASE_SELECTION_R1` with seed/candidate scopes.

It then runs on the machine where the actual audio files are mounted.

## Pipeline

```text
private snapshot + curated case specs
→ read actual local audio bytes
→ compute verified content SHA-256
→ decode actual audio with BaselineLibrosaMIR
→ normalize provider result
→ require positive duration evidence
→ build path-free MusicDNARevision using verified content SHA-256
→ derive explicit phase-scoped TransitionContext
→ generate/persist context-specific TransitionAssessment adjacency
→ run strict greedy and bounded beam from identical evidence
→ require a real reviewable path from both planners
→ reject identical greedy/beam path pairs as non-informative
→ build deterministic blind A/B assignments
→ emit private runtime manifest + strategy-hidden reviewer packet
```

## Identity and provenance boundary

The source workbook calls its 64-hex field `File Signature`, but R1 does not assume undocumented hash semantics. The value is retained as opaque `inventory_file_signature` provenance only.

Runtime content identity is independently computed from the actual local file bytes:

```text
content_identity = sha256:<verified byte-wise SHA-256>
input_identity   = sha256:<verified byte-wise SHA-256>
```

The private runtime manifest records both `inventory_file_signature` and `content_sha256`. Equality between them is neither assumed nor required unless the upstream inventory-signature contract is separately documented.

## Truth boundaries

- Snapshot BPM/key/energy remain curation metadata only; they are not substituted when audio decoding/MIR fails.
- Positive duration is measured from decoded local audio.
- Missing/unreadable local audio fails closed before Music DNA is created.
- TransitionAssessment remains the sole pairwise transition authority.
- No metadata-only heuristic is allowed to masquerade as TransitionAssessment.
- Greedy and beam receive the same persisted evidence, intent, root state, ranking policy and base TransitionContext.
- Whole-track Music DNA fallback is permitted when no rhythmic-structure revision exists; missing phrase/bass/vocal/spectral evidence remains explicit rather than fabricated.
- A case is not admitted to blind review when either planner has no path, reports missing evidence/budget exhaustion, fails engineering acceptance, or both planners produce the same path.
- Human review cannot activate optimizer/ranking policy or Personal DJ Model training.

## Privacy

The runtime manifest contains absolute local paths and is `CASER_PRIVATE_EVIDENCE` only. The reviewer packet contains display names and anonymous `PLAN_A/PLAN_B` ordering but no algorithm identity and no absolute file paths. Neither private snapshot nor runtime manifest belongs in the public repository.

## Runtime database

The command requires an explicit dedicated SQLite path. TransitionAssessment persistence remains append-only and integrity-checked through `MusicIntelligenceRepository`.

## Command

```bash
python scripts/materialize_real_library_pilot_r1.py \
  --snapshot /path/to/APPLAYLIST_LOCAL_LIBRARY_SNAPSHOT_R1_2026-08-17.json \
  --cases /path/to/APPLAYLIST_CURATED_CASE_SELECTION_R1_2026-08-17.json \
  --output-dir /path/to/private/pilot-output \
  --database /path/to/private/applaylist-real-library-r1.sqlite3 \
  --generated-at 2026-08-17T04:00:00+02:00 \
  --blinding-seed '<private-seed>'
```

## Outputs

- `APPLAYLIST_REAL_LIBRARY_RUNTIME_EVIDENCE_R1.private.json`
- `APPLAYLIST_BLINDED_HUMAN_DJ_REVIEW_PACKET_R1.json`
- dedicated SQLite TransitionAssessment evidence database

The command returns SHA-256 digests for both JSON outputs.

## Non-goals

No release/deploy, no production activation, no automatic learning, no Personal DJ Model training, no graph/vector database, no LLM path authority, and no public publication of local filesystem paths.
