# APPLAYLIST — Provider Analysis Rollout Plan

## Status

Planned rollout. Default remains legacy.

## Purpose

This document defines how APPLAYLIST should safely integrate the provider-based analysis path into API/job/runtime layers.

The goal is controlled adoption without breaking existing behavior.

## Current Default

The default analysis path remains:

- services.analysis.analyzer.AudioAnalyzer
- existing API behavior
- existing job behavior
- existing persistence behavior

The provider path exists as a sidecar.

## Feature Flag

Provider analysis is enabled only when:

APPLAYLIST_PROVIDER_ANALYSIS_ENABLED=1

Default behavior:

APPLAYLIST_PROVIDER_ANALYSIS_ENABLED unset -> legacy

Invalid values fail closed to legacy.

## Existing Safe Path

Provider path currently flows through:

- core.analysis.provider_feature_flags
- services.analysis.routed_analysis_service
- services.analysis.provider_analysis_service
- core.analysis.provider_orchestrator
- core.analysis.provider_registry
- core.analysis.provider_baseline

## Rollout Phases

### Phase A — Internal Service Readiness

Status: current target.

Requirements:

- provider hardening verify passes
- routed analysis service tests pass
- feature flag default is legacy
- provider mode can run baseline provider
- full test suite passes

### Phase B — Job Layer Integration

Add routed service to job execution path behind feature flag.

Rules:

- legacy path remains default
- job logs must include selected mode
- provider failures must be controlled ProviderError failures
- no raw optional dependency tracebacks

### Phase C — API Integration

Expose provider route behavior carefully.

Options:

1. keep existing endpoint behavior unchanged
2. add internal query/header override only for development
3. add provider metadata endpoint
4. add availability endpoint

Do not silently change existing API response shape.

### Phase D — Observability

Add structured fields:

- analysis_mode
- provider
- backend
- fallback_used
- provider_error_code
- duration_ms

### Phase E — Default Provider Rollout

Only after production-like verification:

- turn provider flag on in local
- turn provider flag on in staging
- compare outputs
- verify persistence compatibility
- then consider provider as default

## Hard Stop Conditions

Do not enable provider path by default if:

- tests fail
- provider verify fails
- optional dependency import happens during API startup
- response shape changes unexpectedly
- provider output is not normalized
- persistence records diverge without migration plan

## Rollback

Disable provider path:

APPLAYLIST_PROVIDER_ANALYSIS_ENABLED=0

or unset it.

Legacy path remains available.

## Definition of Done

Provider rollout is ready for first API/job integration when:

- scripts/verify_provider_hardening.sh passes
- scripts/verify_provider_rollout_readiness.sh passes
- full test suite passes
- feature flag default is legacy
- routed service can run provider mode explicitly
