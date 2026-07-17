from __future__ import annotations

import pytest


_REQUIRED_ROUTES = {
    "/health",
    "/jobs/{job_type}",
    "/jobs/{job_id}",
    "/pipeline/run",
}


def _route_paths(router_or_app) -> list[str | None]:
    return [getattr(route, "path", None) for route in router_or_app.routes]


@pytest.fixture(autouse=True)
def _diagnose_route_factory_state(request):
    """Identify whether route factories or application inclusion lose state."""
    yield

    import api.main as main_module

    health_router = main_module.create_health_router()
    jobs_router = main_module.create_jobs_router()
    pipeline_router = main_module.create_pipeline_router()
    app = main_module.create_app()

    paths = set(_route_paths(app))
    missing = _REQUIRED_ROUTES - paths
    assert not missing, (
        f"{request.node.nodeid} route factory state invalid; "
        f"missing={sorted(missing)}; "
        f"health={_route_paths(health_router)}; "
        f"jobs={_route_paths(jobs_router)}; "
        f"pipeline={_route_paths(pipeline_router)}; "
        f"app={_route_paths(app)}; "
        f"factory_modules=("
        f"{main_module.create_health_router.__module__},"
        f"{main_module.create_jobs_router.__module__},"
        f"{main_module.create_pipeline_router.__module__})"
    )
