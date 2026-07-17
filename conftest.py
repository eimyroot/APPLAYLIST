from __future__ import annotations

import pytest


_REQUIRED_ROUTES = {
    "/health",
    "/jobs/{job_type}",
    "/jobs/{job_id}",
    "/pipeline/run",
}


@pytest.fixture(autouse=True)
def _diagnose_route_factory_state(request):
    """Identify the first test that corrupts application factory route state."""
    yield

    from api.main import create_app

    app = create_app()
    paths = {getattr(route, "path", None) for route in app.routes}
    missing = _REQUIRED_ROUTES - paths
    assert not missing, (
        f"{request.node.nodeid} corrupted application route state; "
        f"missing={sorted(missing)}"
    )
