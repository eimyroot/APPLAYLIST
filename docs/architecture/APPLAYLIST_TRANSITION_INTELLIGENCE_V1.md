---
id: ARCH-TRANSITION-INTELLIGENCE-V1
title: APPLAYLIST Transition Intelligence V1
status: PROPOSED
owner: APPLAYLIST Engineering
created: 2026-07-23
updated: 2026-07-26
supersedes: null
related:
  - WB-049A
---

# APPLAYLIST Transition Intelligence V1

## Truth status

This document describes a local dirty-worktree candidate, not a committed canonical capability.

Current evidence:

- **VERIFIED:** canonical HEAD `bde0d2c0f159e961beaa6e35753239ded911af25`,
- **VERIFIED:** dirty-worktree `git diff --check` passed,
- **VERIFIED:** Python syntax audit reported zero failures,
- **VERIFIED:** redacted secret scan reported zero findings,
- **NOT VERIFIED:** targeted transition behavior tests,
- **NOT VERIFIED:** repository-wide regression,
- **NOT VERIFIED:** security review of the transition implementation,
- **NOT VERIFIED:** isolated commit, Git bundle and publication evidence,
- **NOT VERIFIED:** runtime integration and DJ workflow validation.

The document may move to `IMPLEMENTED` only after the transition foundation is isolated, tested and committed as a governed Work Block.

## Product invariant

APPLAYLIST does not reject a track because its key is distant or unavailable.

It evaluates a directional transition, reports evidence and uncertainty, recommends a performance strategy, and leaves the final decision to the DJ.

## Local dirty-worktree candidate

The current worktree contains uncommitted code intended to provide:

- deterministic legacy scoring boundary without hidden network access,
- explicit optional external features,
- multidimensional versioned `TransitionAssessment`,
- stable deterministic analysis and assessment identifiers,
- measured-confidence-only handling; missing confidence remains unavailable,
- tonal weights constrained to 10–25% by transition profile,
- SAFE / POSSIBLE / CREATIVE / RISKY / UNKNOWN classification,
- recommendation and explanation linked to the same assessment,
- separate `UserTransitionDecision` linkage contract,
- shadow-only Transition Intelligence evaluation,
- preserved legacy composer ranking scale,
- no database migration,
- no hard key filter.

These behaviors are not canonical product capabilities until Pilot B verifies the complete transition foundation slice and its unit tests.

## Honest capability boundaries

The current repository does not yet provide trustworthy segment-level:

- phrase boundaries,
- vocal activity,
- bass activity,
- overlap windows.

These dimensions remain explicitly unavailable and reduce evidence coverage. Whole-track harmonic ratio must not be used as bass-collision evidence. Missing provider confidence must not be replaced with invented measurement confidence.

Without phrase evidence, recommendations must not claim a precise beat overlap. They require preview and manual transition-point selection.

## Target shadow-mode boundary

The candidate Transition Intelligence produces a 0–100 assessment score. Composer ranking remains on its legacy approximate 0–3 scale plus energy dramaturgy contribution.

The new score must not replace composer ranking until a separate versioned composition policy normalizes and explains every contribution and the integration Work Block passes its own regression and rollback gates.

## Non-goals

This document does not claim:

- production readiness,
- completed phrase, vocal or bass intelligence,
- canonical composer integration,
- validated frontend behavior,
- released or runtime-verified capability.

## Rollback

Before Pilot B changes or commits transition code, create a fresh verified checkpoint of `/Users/eimyna/APPLAYLIST`.

After an isolated transition-foundation commit exists, prefer an exact `git revert` of that commit. Before a commit exists, restore only from the fresh verified checkpoint. The historical Google Drive repository is not an authoritative rollback source.
