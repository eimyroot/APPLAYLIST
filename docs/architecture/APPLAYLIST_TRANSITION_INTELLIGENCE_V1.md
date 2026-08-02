---
id: ARCH-TRANSITION-INTELLIGENCE-V1
title: APPLAYLIST Transition Intelligence V1
status: IMPLEMENTED
owner: APPLAYLIST Engineering
created: 2026-07-23
updated: 2026-07-30
supersedes: null
related:
  - ../../STATUS.md
  - ../../ROADMAP.md
  - APPLAYLIST_RHYTHMIC_STRUCTURE_EVIDENCE_V1.md
---

# APPLAYLIST Transition Intelligence V1

## Truth status

The Transition Intelligence **foundation code is implemented and committed** on the current
Bundle-26 development line. This does not grant runtime authority.

Current boundary:

```text
RUNTIME_AUTHORITY=NONE
TRANSITION_INTELLIGENCE_ACTIVATION=NONE
WB006D=HOLD
```

## Product invariant

APPLAYLIST does not reject a track merely because its key is distant or unavailable.

It evaluates a directional transition, reports evidence and uncertainty, recommends a performance
strategy, and leaves the final decision to the DJ.

## Implemented foundation

The committed foundation provides versioned transition assessment/scoring concepts,
confidence-aware dimensions, classification, recommendation/explainability support, and user
decision contracts.

The tonal contribution is bounded as one dimension rather than a hard key gate.

## Current evidence limitations

The repository does not yet provide accepted segment-level:

- downbeat evidence,
- phrase boundaries,
- vocal activity,
- bass activity,
- directional overlap windows.

WB006C adds independent source-bound **beat-grid shadow evidence** only. Its confidence heuristics
remain uncalibrated and it does not activate Transition Intelligence.

Without accepted phrase/segment evidence, recommendations must not claim a precise beat overlap
or fabricated collision measurement.

## Composer boundary

Transition assessment and legacy composer ranking remain separate. New transition scoring must not
silently replace composer ranking. Composer integration requires its own shadow comparison,
activation flag, regression evidence, and rollback.

## Non-claims

This document does not claim:

- completed phrase, vocal or bass intelligence;
- calibrated real-world rhythmic accuracy;
- canonical composer activation;
- validated desktop/product UI behavior;
- release readiness.

## Next evidence

Follow `ROADMAP.md`: close EPIC-002, resolve EPIC-003 contract drift, then resume EPIC-006 with
independent downbeat evidence before phrase/structure acceptance.
