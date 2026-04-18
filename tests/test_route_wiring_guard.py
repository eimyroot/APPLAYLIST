from api.main import app


def test_required_routes_present() -> None:
    paths = {getattr(route, "path", None) for route in app.routes}
    required = {
        "/health",
        "/jobs/{job_type}",
        "/jobs/{job_id}",
        "/pipeline/run",
    }
    missing = required - paths
    assert not missing, f"Missing routes: {sorted(missing)}"
