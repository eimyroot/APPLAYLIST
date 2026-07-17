# Bundle 27 — Production Authentication Fail-Closed

## Goal

Guarantee that production write routes cannot become unauthenticated because environment configuration is missing or explicitly disables authentication.

## Confirmed defect

The previous `SecuritySettings.auth_enabled` implementation returned `False` in production when both `AUTH_ENABLED` and `API_KEY` were unset. `ApiKeyAuthMiddleware` then bypassed authentication entirely.

## Security contract

- `APP_ENV=production|prod` always enables API-key enforcement
- `AUTH_ENABLED=false` cannot disable authentication in production
- a missing production `API_KEY` returns HTTP 503 with `auth_misconfigured`
- a missing or incorrect configured key returns HTTP 401
- key comparison uses `hmac.compare_digest`
- safe read methods remain available
- development may explicitly disable authentication

## Configuration

The production example no longer ships with `API_KEY=change-me`. Operators must generate a strong secret. Leaving the value empty is safe because write routes fail closed with HTTP 503.

## Non-goals

- no JWT or identity redesign
- no route authorization expansion
- no CORS change
- no API response-shape change

## Verification contract

- production without a key rejects write requests
- production with `AUTH_ENABLED=false` still enforces authentication
- production with a valid key accepts write requests
- health remains available without a key
- development auth-disable behavior remains supported
- Python 3.11 and 3.12 CI must pass before merge

## Rollback

Revert the future Bundle 27 squash commit. No database or data rollback is required.
