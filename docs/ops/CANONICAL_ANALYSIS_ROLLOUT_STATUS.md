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
| WB004C | Bounded non-live profile and writer receipts | `097c9aac266d655b55cade4f510173f39429bae6` | PR #89 merged as `af31f0efa2c4e84840703ad3b76e6158dc1e08f2` | VERIFIED MERGED |
| WB004D | Canonical-versus-legacy comparison receipts | `5da9428415a5da58cbc6a8a10308b8e740725912` | PR #90 merged as `996d38f7a45cf7bafe9b0643fb34004353b717ff` | VERIFIED MERGED |
| WB004E | Isolated default-off canonical shadow reader core | `df42b7a054802a3a08b2e2a696feae1b75b82f2b` | PR #93 merged as `fa77675ec91ffb70a0e699cd377dab6b28975f92` | VERIFIED MERGED |
| WB004F | Canonical shadow-read parity campaign | not started | none | NEXT — NOT STARTED |
| WB004G | Authority decision / controlled cutover design | not started | none | PLANNED |

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
PR #89
  └─ bounded non-live activation + JSONL writer receipts
       ↓
PR #90
  └─ canonical-versus-legacy comparison receipts
       ↓
PR #92
  └─ WB004D post-merge documentation reconciliation
       ↓
PR #93
  └─ isolated default-off canonical shadow reader core
       ↓
NEXT: WB004F representative canonical shadow-read parity campaign
```

## Current authority boundary

```text
LEGACY_ANALYSIS_AUTHORITY=ACTIVE
CANONICAL_WRITER_DEFAULT=OFF
CANONICAL_WRITER_PRODUCTION=FAIL_CLOSED_OFF
CANONICAL_COMPARISON_DEFAULT=OFF
CANONICAL_SHADOW_READER_CORE=MERGED_DEFAULT_OFF
CANONICAL_READER_PRODUCT_PATH=NONE
CANONICAL_READER_ACTIVATION=NONE
BACKFILL=NONE
RUNTIME_AUTHORITY_SWITCH=NONE
TRANSITION_INTELLIGENCE_ACTIVATION=NONE
WB006D=HOLD
```

## Verified WB004D evidence

```text
IMPLEMENTATION_COMMIT=5da9428415a5da58cbc6a8a10308b8e740725912
PR=90
MERGE_COMMIT=996d38f7a45cf7bafe9b0643fb34004353b717ff
FULL_REGRESSION=208_PASSED
RESTORE_SMOKE=PASS
SECURITY_GATE=PASS
CONTEXT_AWARE_DIFF_REVIEW=PASS
FORBIDDEN_SCOPE_FINDINGS=0
LIVE_DB_UNCHANGED=VERIFIED
CANONICAL_READER_ACTIVATION=NONE
RUNTIME_AUTHORITY=NONE
BACKFILL=NONE
```

## Verified WB004E evidence

```text
IMPLEMENTATION_COMMIT=df42b7a054802a3a08b2e2a696feae1b75b82f2b
PR=93
MERGE_COMMIT=fa77675ec91ffb70a0e699cd377dab6b28975f92
FOCUSED_TESTS=18_PASSED
FULL_REGRESSION=226_PASSED
RESTORE_SMOKE=PASS
SECURITY_GATE=PASS
AST_BOUNDARY_REVIEW=PASS
EXISTING_PRODUCT_PATH_INTEGRATION_FINDINGS=0
CANONICAL_READER_PRODUCT_PATH=NONE
CANONICAL_READER_ACTIVATION=NONE
RUNTIME_AUTHORITY_SWITCH=NONE
BACKFILL=NONE
```

## Local evidence references

Evidence directories remain local and are not product runtime inputs:

- `APPLAYLIST_WB004B_CANONICAL_SHADOW_WRITER_ACTIVATION_VERIFY_20260803T012644Z`;
- `APPLAYLIST_WB004C_EXACT_FIVE_ROW_CLEANUP_20260803T021109Z`;
- `APPLAYLIST_WB004C_BOUNDED_NONLIVE_WRITER_OBSERVABILITY_RESUME_V3_20260803T022355Z`;
- `APPLAYLIST_WB004D_CANONICAL_LEGACY_COMPARISON_RESUME_V3_*`;
- `APPLAYLIST_WB004D_PR90_REVIEW_RESUME_V2_20260806T011917Z`;
- `APPLAYLIST_WB004D_PR90_MERGE_CLOSURE_RESUME_V2_20260806T021836Z`;
- `APPLAYLIST_WB004D_POSTMERGE_DOC_RECONCILIATION_AUDIT_20260806T023117Z`;
- `APPLAYLIST_WB004E_CANONICAL_SHADOW_READER_AUDIT_DESIGN_20260806T191133Z`;
- `APPLAYLIST_WB004E_CANONICAL_SHADOW_READER_CORE_IMPLEMENTATION_20260806T193631Z`;
- `APPLAYLIST_WB004E_CANONICAL_SHADOW_READER_CORE_PR93_REVIEW_RESUME_V3_20260806T200234Z`.

Each evidence directory contains a `FINAL_RECEIPT.txt` and `SHA256SUMS.txt` when the producing
bundle reached closure.

## Next gates

1. Reconcile and publish this documentation-only WB004E post-merge update.
2. Run WB004F as a separate representative canonical shadow-read parity campaign.
3. Keep the merged WB004E reader core disconnected from product request paths during WB004F.
4. Make no authority decision before representative WB004F evidence and WB004G authorization.
5. Keep canonical reader activation, backfill and runtime authority switch disabled.
6. Keep WB006D on hold as an independent EPIC-006 work item.
