---
id: FOUNDATION-ROADMAP
title: APPLAYLIST Product Roadmap
status: ACCEPTED
owner: APPLAYLIST Engineering
created: 2026-07-30
updated: 2026-08-03
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
| EPIC-004 | Provider framework, canonical shadow persistence and observability | IN PROGRESS — WB004C verified locally, publication pending |
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
7. WB004A — default-off, non-authoritative runtime writer.
8. WB004B — disposable activation verification.
9. WB004C — bounded non-live activation profile and success/failure receipts; verified locally,
   publication pending.

## Immediate sequence

1. Publish WB004C through a reviewed pull request.
2. WB004D — canonical-versus-legacy comparison receipts and mismatch classification.
3. WB004E — canonical reader design and shadow-read verification without authority.
4. Make an explicit authority decision only after writer reliability and comparison evidence.
5. Resume EPIC-006 with independent downbeat evidence.
6. Add phrase/structure acceptance only after downbeat evidence is trustworthy.
7. Continue to vocal/bass collision intelligence.
8. Integrate with composer in shadow mode before any opt-in runtime activation.

## Activation invariant

Legacy analysis remains authoritative. Canonical persistence is non-authoritative and disabled in
production. The canonical reader, backfill, authority switch, Transition Intelligence runtime
activation, and WB006D remain disabled until separately authorized and verified.

GitHub Actions are not an authoritative gate for the current local-first work blocks.
