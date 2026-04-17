from pathlib import Path

p = Path("api/main.py")
text = p.read_text(encoding="utf-8")

imports = [
    "from api.security.auth_gate import ApiKeyAuthMiddleware",
]

for imp in imports:
    if imp not in text:
        lines = text.splitlines()
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                insert_at = i + 1
        lines.insert(insert_at, imp)
        text = "\n".join(lines) + "\n"

marker = 'app.add_middleware(RequestContextMiddleware)\n'
if marker in text and 'app.add_middleware(ApiKeyAuthMiddleware)\n' not in text:
    text = text.replace(
        marker,
        marker + "app.add_middleware(ApiKeyAuthMiddleware)\n",
        1,
    )

p.write_text(text, encoding="utf-8")
print("api/main.py patched for bundle 13")
