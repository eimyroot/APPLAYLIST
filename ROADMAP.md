---
id: FOUNDATION-ROADMAP
title: APPLAYLIST Product Roadmap
status: ACCEPTED
owner: APPLAYLIST Engineering
created: 2026-07-30
updated: 2026-08-06
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
| EPIC-004 | Canonical persistence rollout | IN PROGRESS — WB004D merged; WB004E read-only audit/design next |
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

## Immediate sequence

1. WB004E — canonical shadow reader read-only audit/design and disposable verification plan.
2. Implement WB004E only after separate authorization.
3. WB004F — representative canonical shadow-read parity campaign.
4. WB004G — explicit authority decision and controlled cutover design.
5. Make no authority switch before WB004F evidence and WB004G authorization.
6. Resume EPIC-006 with independent downbeat evidence.
7. Add phrase/structure acceptance only after downbeat evidence is trustworthy.
8. Continue to vocal/bass collision intelligence.
9. Integrate with composer in shadow mode before any opt-in runtime activation.

## EPIC-004 rollout sequence

```text
WB004A  Default-off canonical shadow writer                     VERIFIED MERGED
WB004B  Disposable writer activation verification               VERIFIED
WB004C  Bounded non-live writer + observability receipts        VERIFIED MERGED
WB004D  Canonical-versus-legacy comparison receipts             VERIFIED MERGED
WB004E  Canonical shadow reader design + verification           NEXT — NOT STARTED
WB004F  Canonical shadow-read parity campaign                   PLANNED
WB004G  Authority decision / controlled cutover design          PLANNED
```

## Activation invariant

Legacy analysis remains authoritative. Canonical persistence is non-authoritative and disabled in
production. The canonical reader, backfill, authority switch, Transition Intelligence runtime
activation, and WB006D remain disabled until separately authorized and verified.

GitHub Actions are not an authoritative gate for the current local-first work blocks.
