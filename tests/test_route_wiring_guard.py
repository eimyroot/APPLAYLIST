from api.main import app


def test_required_routes_present() -> None:
    """Verify the public API contract without relying on route-tree internals."""
    paths = app.openapi().get("paths", {})
    required = {
        "/health": {"get"},
        "/jobs/{job_type}": {"post"},
        "/jobs/{job_id}": {"get"},
        "/pipeline/run": {"post"},
    }

    missing_paths = set(required) - set(paths)
    assert not missing_paths, f"Missing routes: {sorted(missing_paths)}"

    missing_methods = {
        route: sorted(methods - set(paths[route]))
        for route, methods in required.items()
        if methods - set(paths[route])
    }
    assert not missing_methods, f"Missing route methods: {missing_methods}"
