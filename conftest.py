from __future__ import annotations

import inspect

_REQUIRED_ROUTES = {
    "/health",
    "/jobs/{job_type}",
    "/jobs/{job_id}",
    "/pipeline/run",
}


def _describe_callable(value) -> str:
    target = getattr(value, "__func__", value)
    return (
        f"{getattr(target, '__module__', '?')}."
        f"{getattr(target, '__qualname__', type(target).__qualname__)}"
    )


def _describe_routes(router_or_app) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for route in router_or_app.routes:
        rows.append(
            {
                "path": getattr(route, "path", None),
                "type": f"{type(route).__module__}.{type(route).__qualname__}",
                "name": getattr(route, "name", None),
                "repr": repr(route)[:180],
            }
        )
    return rows


def pytest_collection_finish(session) -> None:
    """Fail once with enough evidence to identify collection-time FastAPI mutation."""
    import fastapi
    import fastapi.routing
    import api.main as main_module

    health_router = main_module.create_health_router()
    jobs_router = main_module.create_jobs_router()
    pipeline_router = main_module.create_pipeline_router()
    app = main_module.create_app()

    paths = {getattr(route, "path", None) for route in app.routes}
    missing = _REQUIRED_ROUTES - paths
    if not missing:
        return

    health_route = health_router.routes[0]
    diagnostics = {
        "missing": sorted(missing),
        "main_fastapi_class": (
            f"{main_module.FastAPI.__module__}.{main_module.FastAPI.__qualname__}"
        ),
        "fastapi_class_same": main_module.FastAPI is fastapi.FastAPI,
        "app_include_router": _describe_callable(app.include_router),
        "internal_include_router": _describe_callable(app.router.include_router),
        "app_include_source": inspect.getsource(app.include_router.__func__)[:500],
        "internal_include_source": inspect.getsource(app.router.include_router.__func__)[:500],
        "health_route_is_current_api_route": isinstance(
            health_route, fastapi.routing.APIRoute
        ),
        "health_routes": _describe_routes(health_router),
        "jobs_routes": _describe_routes(jobs_router),
        "pipeline_routes": _describe_routes(pipeline_router),
        "app_routes": _describe_routes(app),
    }
    raise AssertionError(f"FastAPI route inclusion corrupted during collection: {diagnostics!r}")
