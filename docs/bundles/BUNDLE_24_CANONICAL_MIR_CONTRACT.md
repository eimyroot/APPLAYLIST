# Bundle 24 — Canonical MIR Contract + Provider Adapter

## Intent
Standardize analyzer outputs into one canonical MIR contract.

## Included
- `core/analysis/contracts.py`
- `core/analysis/adapter.py`
- `tests/unit/test_analysis_contracts.py`

## Canonical fields
- path
- provider
- bpm
- bpm_confidence
- key
- key_confidence
- energy
- loudness_db
- duration_seconds
- genre_hint
- analysis_status
- analysis_version

## Why
Different analyzers expose BPM/key/energy/duration in different shapes.
This bundle creates a stable backend contract so the rest of APPLAYLIST can depend on one predictable schema.

## Notes
This is intentionally adapter-first and low-risk.
The next step is to wire this contract into the existing analyzer pipeline and API responses.
