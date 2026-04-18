from __future__ import annotations

import sqlite3
from pathlib import Path
from core.config.settings import get_settings


def _sqlite_path_from_url(database_url: str) -> str:
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        return database_url[len(prefix):]
    return database_url


def get_sqlite_connection() -> sqlite3.Connection:
    settings = get_settings()
    db_path = _sqlite_path_from_url(settings.database_url)

    path_obj = Path(db_path)
    if path_obj.parent and str(path_obj.parent) not in ("", "."):
        path_obj.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
