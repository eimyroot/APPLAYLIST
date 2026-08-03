# Canonical Analysis Rollout Status

## Purpose

This document links APPLAYLIST work bundles to their repository commits, GitHub publication state,
runtime authority and local verification evidence. It is the operational index for the canonical
analysis persistence rollout.

## Evidence matrix

| Work bundle | Capability | Local commit / baseline | GitHub evidence | State |
| --- | --- | --- | --- | --- |
| WB003A | Canonical contract authority | included in PR #86 history | PR #86 merged | VERIFIED MERGED |
| WB003B | Typed provider boundary | included in PR #86 history | PR #86 merged | VERIFIED MERGED |
| WB003C1 | Legacy canonical projection | included in PR #86 history | PR #86 merged | VERIFIED MERGED |
| WB003C3B | SQLite migration controls | `c2b27ff6e5f03bbc078ec20dd246711480359429` | PR #86 merged | VERIFIED MERGED |
| WB003C4 | Additive canonical schema v1 | `e20ff56c67cace83ab78df3e3a491719dba59cf5` | PR #86 merged | VERIFIED MERGED |
| WB003C5 | Inactive persistence repository | `3f0f3f465b66bbdd58a58cedd336f2feb1d19c39` | PR #87 merged | VERIFIED MERGED |
| WB004A | Default-off shadow writer | `ca8592bae4934cff1a0166ae239c634b8eea07d1` | PR #88 merged | VERIFIED MERGED |
| WB004B | Disposable activation verification | no repository commit | local evidence only | VERIFIED, NON-PUBLISHABLE |
| WB004C | Bounded non-live profile and receipts | `097c9aac266d655b55cade4f510173f39429bae6` | push/PR pending | VERIFIED LOCAL |

## Current publication graph

```text
PR #86
  └─ canonical contracts + schema/migration foundation
       ↓
PR #87
  └─ inactive canonical persistence repository
       ↓
PR #88
  └─ default-off canonical shadow writer
       ↓
WB004B
  └─ disposable runtime verification only
       ↓
WB004C local commit 097c9aa
  └─ bounded non-live activation + JSONL success/failure receipts
       ↓
PENDING: push → draft PR → review → merge
```

## Current authority boundary

```text
LEGACY_ANALYSIS_AUTHORITY=ACTIVE
CANONICAL_WRITER_DEFAULT=OFF
CANONICAL_WRITER_PRODUCTION=FAIL_CLOSED_OFF
CANONICAL_READER_ACTIVATION=NONE
BACKFILL=NONE
RUNTIME_AUTHORITY_SWITCH=NONE
TRANSITION_INTELLIGENCE_ACTIVATION=NONE
WB006D=HOLD
```

## Local evidence references

Evidence directories remain local and are not product runtime inputs:

- `APPLAYLIST_WB004B_CANONICAL_SHADOW_WRITER_ACTIVATION_VERIFY_20260803T012644Z`;
- `APPLAYLIST_WB004C_EXACT_FIVE_ROW_CLEANUP_20260803T021109Z`;
- `APPLAYLIST_WB004C_BOUNDED_NONLIVE_WRITER_OBSERVABILITY_RESUME_V3_20260803T022355Z`.

Each evidence directory contains a `FINAL_RECEIPT.txt` and `SHA256SUMS.txt`. The cleanup evidence
also preserves a consistent contaminated pre-cleanup SQLite backup.

## Next gates

1. Publish WB004C without changing its verified commit content.
2. Verify the remote branch SHA and open a draft PR.
3. Review and merge WB004C.
4. Design WB004D comparison receipts.
5. Do not activate a canonical reader or change runtime authority in WB004D.
