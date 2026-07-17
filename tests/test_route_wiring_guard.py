from api.main import create_app


def test_required_routes_present() -> None:
    """Validate public route wiring without depending on FastAPI internals."""
    app = create_app()
    paths = set(app.openapi().get("paths", {}))
    required = {
        "/health",
        "/jobs/{job_type}",
        "/jobs/{job_id}",
        "/pipeline/run",
    }
    missing = required - paths
    assert not missing, f"Missing routes: {sorted(missing)}"
