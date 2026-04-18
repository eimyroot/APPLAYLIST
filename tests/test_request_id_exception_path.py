from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.core.observability import (
    configure_observability,
    http_exception_handler,
    log_request_response,
    unhandled_exception_handler,
    validation_exception_handler,
)
from api.middleware.request_context import RequestContextMiddleware


def build_app() -> FastAPI:
    configure_observability()
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.middleware("http")(log_request_response)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/boom")
    def boom():
        raise RuntimeError("bundle14 boom")

    return app


def test_exception_path_includes_request_id_header_and_body() -> None:
    app = build_app()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    rid_body = body["error"]["request_id"]
    rid_header = response.headers.get("X-Request-ID")

    assert rid_body
    assert rid_header
    assert rid_body == rid_header
