# Bundle 38 — Configured Composition Authority Selector

## Status

Implementation candidate. The default remains `legacy`.

## Goal

Allow a controlled operator rollout of canonical composition without adding a per-request API switch or silently changing existing installations.

## Configuration

```env
COMPOSITION_AUTHORITY=legacy
```

Allowed values are:

- `legacy`,
- `canonical`.

The selector is loaded through a dedicated typed settings model that reads process environment variables and the project `.env` file. Unknown values fail validation.

A safe standalone example is stored at:

```text
config/examples/composition-authority.env.example
```

The main `.env.example` was not rewritten in this bundle because it contains historical secret fields and the repository write safety gate rejected a full-file replacement.

## Selection precedence

1. Explicit `composition_authority` dependency injection.
2. Explicit legacy `composer`, `exporter` or `run_id_factory` dependencies.
3. Configured `COMPOSITION_AUTHORITY`.
4. Default `legacy`.

Configuration therefore cannot override explicit test or embedding dependencies.

## Canonical mode

With:

```env
COMPOSITION_AUTHORITY=canonical
ENABLE_COMPOSITION_COMPARISON=false
```

default `OrchestratorPipeline` construction selects `CanonicalCompositionAuthority`, which delegates through the validated canonical runner and export service.

There is no fallback to legacy when canonical execution fails.

## Comparison restriction

Comparison observability treats the authoritative playlist as a legacy baseline. Running it while canonical is authoritative would create semantically invalid evidence. The combination is therefore rejected fail-closed:

```env
COMPOSITION_AUTHORITY=canonical
ENABLE_COMPOSITION_COMPARISON=true
```

## Compatibility

The following remain unchanged:

- API route and request schema,
- top-level pipeline response shape,
- default legacy behavior,
- explicit composer/exporter/run-ID injection,
- database schema,
- exporter artifact format.

## Rollback

Set:

```env
COMPOSITION_AUTHORITY=legacy
```

and restart the process. Code rollback is available by reverting the Bundle 38 squash commit. No data rollback is required.
