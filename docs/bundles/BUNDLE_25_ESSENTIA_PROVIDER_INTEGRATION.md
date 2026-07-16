# Bundle 25 — Essentia Provider Integration

## Summary
Adds a gated Essentia provider integration on top of the provider layer and canonical MIR architecture.

## Why
The system now has provider abstraction and canonical mapping, so the next step is to plug in a real advanced provider without hard-coupling the stack.

## Included
- `core/analysis/provider_essentia.py`
- `core/analysis/provider_registry.py`
- targeted unit tests
- verify script

## Notes
Essentia remains optional and environment-gated in this bundle.
Rich extraction can be expanded later without changing downstream contracts.
