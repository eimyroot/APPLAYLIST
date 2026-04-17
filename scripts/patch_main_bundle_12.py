from pathlib import Path

p = Path("api/main.py")
text = p.read_text(encoding="utf-8")

need_imports = [
    "from starlette.exceptions import HTTPException as StarletteHTTPException",
    "from fastapi.exceptions import RequestValidationError",
    "from api.middleware.request_context import RequestContextMiddleware",
    "from api.core.observability import (",
]
obs_import_block = """from api.core.observability import (
    configure_observability,
    http_exception_handler,
    log_request_response,
    unhandled_exception_handler,
    validation_exception_handler,
)"""

if "from api.middleware.request_context import RequestContextMiddleware" not in text:
    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert_at = i + 1
    block_lines = [
        "from starlette.exceptions import HTTPException as StarletteHTTPException",
        "from fastapi.exceptions import RequestValidationError",
        "from api.middleware.request_context import RequestContextMiddleware",
        obs_import_block,
    ]
    lines[insert_at:insert_at] = block_lines
    text = "\n".join(lines) + "\n"

if "configure_observability()" not in text:
    text = text.replace(
        "app = FastAPI(",
        "configure_observability()\n\napp = FastAPI(",
        1,
    )

if 'app.add_middleware(RequestContextMiddleware)' not in text:
    marker = "apply_security_hardening(app)\n"
    text = text.replace(
        marker,
        marker + "\napp.add_middleware(RequestContextMiddleware)\napp.middleware(\"http\")(log_request_response)\n",
        1,
    )

if "app.add_exception_handler(StarletteHTTPException, http_exception_handler)" not in text:
    text += """
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
"""

p.write_text(text, encoding="utf-8")
print("api/main.py patched for bundle 12")
