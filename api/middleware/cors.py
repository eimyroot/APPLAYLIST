from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.security.settings import SecuritySettings, settings


def install_cors(
    app: FastAPI,
    security_settings: SecuritySettings | None = None,
) -> None:
    """Install the single canonical CORS policy for the application."""
    config = security_settings or settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=config.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
