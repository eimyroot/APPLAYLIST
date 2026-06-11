# APPLAYLIST — Provider Architecture Hardening

## Status

Accepted baseline.

## Purpose

APPLAYLIST must support multiple audio extraction backends without allowing one optional dependency to break the whole system.

## Core Rule

Optional providers must never be imported on the mandatory boot path.

Safe boot path:
- API startup
- config
- routes
- core contracts
- provider registry metadata

Unsafe boot path:
- API startup
- import librosa / essentia / numba / llvmlite
- crash

## Provider Layers

- core/analysis/provider_registry.py = registry and provider selection
- core/analysis/normalize.py = output normalization and defensive defaults
- core/analysis/provider_essentia.py = optional advanced provider
- services/analysis/analyzer.py = application-level analyzer orchestration
- data/repositories/ = persistence boundary

## Provider Contract

Every provider must expose:
- name
- availability check
- extract/analyze function
- normalized output
- clear failure mode

Controlled failure types:
- provider_unavailable
- provider_dependency_missing
- provider_runtime_error
- provider_output_invalid

## Dependency Policy

Mandatory baseline:
- Python >=3.11,<3.13
- soundfile
- numpy
- scipy
- FastAPI
- Pydantic
- SQLite/repositories

Optional advanced dependencies:
- librosa
- numba
- llvmlite
- essentia
- future ML audio backends

## Fallback Policy

Provider selection order:
1. requested provider if available
2. configured default provider
3. safe baseline provider
4. controlled failure

There must be no silent fake success.

## Storage Policy

Only normalized analysis records may be persisted.

Allowed flow:
- provider raw output
- normalize
- validate
- AnalysisRecord
- repository

## Testing Policy

Each provider needs:
- availability test
- normalization test
- successful extraction test when dependency exists
- missing dependency behavior test
- invalid output test
- fallback behavior test

## Phase 2 Definition of Done

- provider files exist
- provider registry imports without optional dependency crash
- tests pass
- verify script passes
- architecture notes are committed
