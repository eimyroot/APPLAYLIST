import api.main as main_module


def test_required_routes_present() -> None:
    """Validate the currently active application after reload-based auth tests."""
    paths = {getattr(route, "path", None) for route in main_module.app.routes}
    required = {
        "/health",
        "/jobs/{job_type}",
        "/jobs/{job_id}",
        "/pipeline/run",
    }
    missing = required - paths
    assert not missing, f"Missing routes: {sorted(missing)}"
