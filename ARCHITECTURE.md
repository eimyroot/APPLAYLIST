---
id: FOUNDATION-ARCHITECTURE
title: APPLAYLIST Architecture
status: ACCEPTED
owner: APPLAYLIST Engineering
created: 2026-07-30
updated: 2026-07-30
supersedes:
  - docs/architecture/APPLAYLIST_PHASE1_ARCHITECTURE.md
related:
  - PRODUCT.md
  - STATUS.md
  - docs/architecture/APPLAYLIST_PROVIDER_ANALYSIS_ROLLOUT.md
  - docs/architecture/APPLAYLIST_RHYTHMIC_STRUCTURE_EVIDENCE_V1.md
---

# APPLAYLIST Architecture

## Source-of-truth rule

For current behavior, use this order:

1. current repository content,
2. Git state,
3. executed local verification,
4. runtime configuration/evidence,
5. CI evidence,
6. architecture and operations documentation,
7. README statements.

Historical bundle documents are evidence of their work block, not automatic authority for the
current runtime.

## Current component boundaries

```text
API
  -> application services
      -> domain/core logic
      -> repositories / SQLite
      -> jobs / workers
      -> analysis providers
      -> composer / transition / explainability
```

Primary directories:

- `api/` — HTTP boundary, routes, middleware and API security;
- `core/` — domain logic, analysis/provider contracts, transition logic and configuration;
- `services/` — application orchestration;
- `data/` — models, repositories and persistence;
- `workers/` — background processing scaffolds;
- `tests/` — regression and contract evidence;
- `docs/` — architecture, operations, governance and work-block evidence;
- `scripts/` — local verification and maintenance tooling.

## Analysis boundary

Heavy audio backends must remain behind explicit provider boundaries and must not become mandatory
API-startup imports.

The current repository still contains analysis-contract drift: `core/analysis/normalize.py`
contains a compatibility fallback for richer analysis types that are not defined by the current
`core/analysis/contracts.py`. This is explicit deferred **EPIC-003** debt and is not resolved by
WB001.

## Transition boundary

Transition assessment, recommendation, explanation, and user decision are separate concerns.
Transition Intelligence runtime activation remains off.

WB006C adds source-bound beat-grid shadow evidence and reconciliation only. It does not provide
accepted downbeat, phrase, structure-segment, vocal, bass, or overlap runtime authority.

## Runtime and data safety

- optional-provider failure must not break mandatory startup;
- missing measurements must not be fabricated;
- source identity and provenance must be preserved where a work block requires them;
- local and production configuration must remain separate;
- public API/schema changes require an explicit isolated work block;
- database migrations require backup and rollback evidence.

## Evolution rule

Documentation/governance structure may be improved independently. Runtime module moves,
contract migrations, provider activation, and desktop integration must remain separate,
testable work blocks.
