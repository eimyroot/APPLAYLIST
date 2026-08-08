---
id: FOUNDATION-ROADMAP
title: APPLAYLIST Product Roadmap
status: ACCEPTED
owner: APPLAYLIST Engineering
created: 2026-07-30
updated: 2026-08-08
supersedes:
  - docs/BUNDLE_PLAN.md
related:
  - STATUS.md
  - docs/ops/CANONICAL_ANALYSIS_ROLLOUT_STATUS.md
---

# APPLAYLIST Product Roadmap

This is the canonical high-level roadmap. Historical bundle plans remain evidence but are not the
current planning authority.

| Epic | Scope | Current state |
| --- | --- | --- |
| EPIC-000 | Repository rescue and consolidation | VERIFIED CLOSED |
| EPIC-001 | Foundation and documentation freeze | VERIFIED CLOSED |
| EPIC-002 | Reproducible local engineering baseline | VERIFIED CLOSED |
| EPIC-003 | Canonical analysis contracts and persistence foundation | VERIFIED CORE CLOSED — schema/repository/writer foundation merged |
| EPIC-004 | Canonical persistence rollout | VERIFIED CLOSED — WB004F inconclusive; WB004G NO_CUTOVER; legacy authority retained |
| EPIC-005 | Transition Intelligence foundation | IMPLEMENTED / runtime activation NONE |
| EPIC-006 | Beat, downbeat, phrase and structure intelligence | IN PROGRESS — WB006C beat-grid shadow merged; WB006D HOLD |
| EPIC-007 | Vocal and bass collision intelligence | PLANNED |
| EPIC-008 | Composer integration | PLANNED |
| EPIC-009 | Library and workflow | PLANNED |
| EPIC-010 | Desktop host and sidecar | PLANNED on the current canonical line |
| EPIC-011 | DJ product UI | PLANNED |
| EPIC-012 | Persistence, decisions and learning | PLANNED |
| EPIC-013 | Security, privacy and observability | CROSS-CUTTING / PARTIAL |
| EPIC-014 | Performance and scale | PLANNED |
| EPIC-015 | Packaging and release | PLANNED |
| EPIC-016 | DJ pilot and product validation | PLANNED |

## Completed canonical persistence sequence

1. WB003A — canonical analysis contract authority.
2. WB003B — typed provider output boundary.
3. WB003C1 — legacy canonical read projection.
4. WB003C3B — SQLite migration safety controls.
5. WB003C4 — additive `canonical_analyses` schema v1 migration.
6. WB003C5 — inactive canonical persistence repository.
7. WB004A — default-off, non-authoritative runtime writer; PR #88 merged.
8. WB004B — disposable activation verification; verification-only.
9. WB004C — bounded non-live activation profile and success/failure receipts; PR #89 merged.
10. WB004D — canonical-versus-legacy comparison receipts and mismatch classification;
    implementation commit `5da9428415a5da58cbc6a8a10308b8e740725912`, PR #90 merged as
    `996d38f7a45cf7bafe9b0643fb34004353b717ff`.
11. WB004E — isolated default-off canonical shadow reader core;
    implementation commit `df42b7a054802a3a08b2e2a696feae1b75b82f2b`, PR #93 merged as
    `fa77675ec91ffb70a0e699cd377dab6b28975f92`; product-path activation remains NONE.
12. WB004F — representative parity audit/campaign attempt closed
    `VERIFIED_INCONCLUSIVE_DATASET_NOT_REPRODUCIBLE`: 18 legacy analyses, zero uniquely mapped
    existing audio sources, canonical seed not executed and parity comparison not executed.
13. WB004G — explicit authority decision: `NO_CUTOVER`; legacy analysis remains authoritative,
    canonical reader activation remains NONE and runtime authority switch remains NONE.

## Immediate sequence

1. Resume EPIC-006 with independent downbeat evidence while `WB006D=HOLD` remains in force until
   separately reviewed and authorized.
2. Add phrase/structure acceptance only after downbeat evidence is trustworthy.
3. Continue to EPIC-007 vocal/bass collision intelligence.
4. Integrate EPIC-008 composer intelligence in shadow mode before any opt-in runtime activation.
5. Keep canonical persistence non-authoritative: canonical reader activation NONE, backfill NONE and
   runtime authority switch NONE.
6. Reopen WB004F/WB004G only when a future bounded dataset provides stable audio-source identity and
   reproducible canonical-versus-legacy overlap evidence.

## EPIC-004 rollout sequence

```text
WB004A  Default-off canonical shadow writer                     VERIFIED MERGED
WB004B  Disposable writer activation verification               VERIFIED
WB004C  Bounded non-live writer + observability receipts        VERIFIED MERGED
WB004D  Canonical-versus-legacy comparison receipts             VERIFIED MERGED
WB004E  Canonical shadow reader core                            VERIFIED MERGED
WB004F  Canonical shadow-read parity evidence                   VERIFIED INCONCLUSIVE — DATASET NOT REPRODUCIBLE
WB004G  Authority / controlled cutover decision                 VERIFIED DECISION — NO_CUTOVER
```

## Activation invariant

Legacy analysis remains authoritative. Canonical persistence remains non-authoritative in product
runtime. The WB004E canonical shadow-reader core is merged but is not connected to a product request
path and is not activated. WB004G explicitly concluded `NO_CUTOVER` because the historical WB004F
dataset could not produce reproducible parity evidence. Backfill, authority switch, Transition
Intelligence runtime activation, and WB006D remain disabled until separately authorized and verified.

GitHub Actions are not an authoritative gate for the current local-first work blocks.
