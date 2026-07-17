from api.main import create_app


def test_required_routes_present() -> None:
    """Validate route wiring on a fresh, isolated application instance."""
    app = create_app()
    paths = {getattr(route, "path", None) for route in app.routes}
    required = {
        "/health",
        "/jobs/{job_type}",
        "/jobs/{job_id}",
        "/pipeline/run",
    }
    missing = required - paths
    assert not missing, f"Missing routes: {sorted(missing)}"
