---
id: FOUNDATION-PRODUCT
title: APPLAYLIST Product Definition
status: ACCEPTED
owner: APPLAYLIST Engineering
created: 2026-07-30
updated: 2026-07-30
supersedes: null
related:
  - VISION.md
  - ARCHITECTURE.md
  - ROADMAP.md
  - STATUS.md
---

# APPLAYLIST Product Definition

## User

The primary user is a DJ preparing, evaluating, and performing transitions across a local music
library.

## Job to be done

Reduce the cognitive and technical cost of evaluating a candidate transition while preserving
creative control. APPLAYLIST should turn measured audio evidence into a directional assessment,
risk explanation, and practical recommendation.

## Current capabilities

The current repository contains backend/API, persistence, job/worker, export, composer,
analysis-provider, transition-foundation, and explainability building blocks.

Important authority boundaries:

- the legacy analysis path remains the default runtime path;
- provider-based analysis exists behind explicit selection/feature boundaries;
- Transition Intelligence foundation code exists, but
  `TRANSITION_INTELLIGENCE_ACTIVATION=NONE`;
- WB006C beat-grid work is shadow evidence only and has no runtime registration;
- downbeat, phrase, segment-level vocal, segment-level bass, and directional overlap evidence are
  not yet accepted product capabilities;
- confidence heuristics that have not been calibrated must not be presented as benchmark-approved.

## Planned capabilities

Planned work includes:

- reproducible local engineering gates,
- canonical analysis-contract consolidation,
- accepted downbeat and phrase evidence,
- structure confidence and directional overlap windows,
- vocal and bass collision intelligence,
- shadow comparison and opt-in composer integration,
- library workflow and desktop host,
- DJ product UI,
- user-decision persistence and learning,
- packaging, release and DJ pilot validation.

## Product behavior

Transition classifications may be `SAFE`, `POSSIBLE`, `CREATIVE`, `RISKY`, or `UNKNOWN`.
No classification automatically forbids a track.

A distant or missing key is never by itself a hard rejection.

## Non-claims

This repository is not currently claiming:

- completed phrase analysis,
- completed vocal/bass collision intelligence,
- active Transition Intelligence runtime authority,
- validated end-user desktop workflow,
- release readiness.
