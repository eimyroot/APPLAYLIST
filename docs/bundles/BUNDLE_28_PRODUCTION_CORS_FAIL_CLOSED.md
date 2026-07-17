# Bundle 28 — Production CORS Fail-Closed

## Goal

Prevent production deployments from starting with wildcard or empty CORS origins and prevent wildcard CORS from being combined with browser credentials.

## Confirmed baseline defect

The active security bootstrap installed `CORSMiddleware` with:

- `ALLOW_ORIGINS=*` by default,
- `allow_credentials=True` unconditionally,
- a production example that also used the wildcard.

The repository also tracked an unimported duplicate `api/middleware/cors 2.py`.

## Implemented contract

- `api/middleware/cors.py` owns the single CORS middleware policy.
- `api/security/bootstrap.py` delegates CORS installation to that module.
- Production requires at least one explicit non-wildcard origin.
- Empty or wildcard production configuration raises `SecurityConfigurationError` during application creation.
- Wildcard may be used only outside production and always disables CORS credentials.
- Explicit allowlists enable credentialed CORS.
- Origins are whitespace-normalized and de-duplicated while preserving order.
- A wildcard cannot be mixed with explicit origins.
- The production env example contains an explicit placeholder origin.
- Remote deletion of `cors 2.py` was blocked by the connector, so the file is neutralized to a compatibility re-export with no independent policy.

## Compatibility

- No endpoint or response schema changes.
- No authentication or authorization changes.
- Development keeps wildcard convenience without credential support.
- Existing explicit local origins remain supported.

## Verification gate

- startup rejection tests for production wildcard and empty configuration,
- normalization and duplicate-removal test,
- wildcard-mixing rejection test,
- allowed production preflight test,
- unlisted production origin rejection test,
- development wildcard response without credential headers,
- Python 3.11 and 3.12 CI,
- compile, critical Ruff and full pytest.

## Rollback

Revert the future Bundle 28 squash commit. There is no database or data rollback.
