#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

echo "== BUNDLE 11B REPAIR START =="

mkdir -p .backup_bundle11b

cp api/main.py ".backup_bundle11b/main.py.bak.$(date +%Y%m%d_%H%M%S)"

python3 << 'PY'
from pathlib import Path
import re

p = Path("api/main.py")
text = p.read_text()

# normalize tabs -> spaces
text = text.replace("\t", "    ")

# remove previous possibly duplicated injected imports
lines = text.splitlines()
filtered = []
seen = set()

dedupe_prefixes = [
    "from api.core.logging_setup import setup_logging",
    "from api.middleware.request_hardening import RequestHardeningMiddleware",
]

for line in lines:
    if any(line.strip() == x for x in dedupe_prefixes):
        key = line.strip()
        if key in seen:
            continue
        seen.add(key)
    filtered.append(line)

text = "\n".join(filtered)

# ensure imports exist near top
prefix = []
if "import os" not in text:
    prefix.append("import os")
if "from api.core.logging_setup import setup_logging" not in text:
    prefix.append("from api.core.logging_setup import setup_logging")
if "from api.middleware.request_hardening import RequestHardeningMiddleware" not in text:
    prefix.append("from api.middleware.request_hardening import RequestHardeningMiddleware")

if prefix:
    text = "\n".join(prefix) + "\n" + text

# remove rogue top-level injected calls before app definition
text = re.sub(r"(?m)^setup_logging\(\)\s*$\n?", "", text)
text = re.sub(r"(?m)^app\.add_middleware\(RequestHardeningMiddleware\)\s*$\n?", "", text)

# fix common broken indentation around install_cors(app)
text = re.sub(r"(?m)^[ ]+install_cors\(app\)\s*$", "install_cors(app)", text)

# inject setup_logging before app = FastAPI(...)
m = re.search(r"(?m)^app\s*=\s*FastAPI\s*\(", text)
if not m:
    raise SystemExit("Could not find app = FastAPI(...) in api/main.py")

app_pos = m.start()
before = text[:app_pos]
after = text[app_pos:]

before = before.rstrip() + "\n\nsetup_logging()\n\n"

text = before + after

# inject middleware after app definition block
m2 = re.search(r"(?ms)^app\s*=\s*FastAPI\s*\(.*?\)\s*", text)
if not m2:
    raise SystemExit("Could not parse FastAPI app block in api/main.py")

app_block = m2.group(0)
rest = text[m2.end():]

middleware_line = "\napp.add_middleware(RequestHardeningMiddleware)\n"
if "app.add_middleware(RequestHardeningMiddleware)" not in text:
    text = text[:m2.end()] + middleware_line + rest

# harden wildcard CORS only when present
text = re.sub(
    r'allow_origins\s*=\s*\[\s*"\*"\s*\]',
    'allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")',
    text
)

# clean accidental 3+ blank lines
text = re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"

p.write_text(text)
print("api/main.py repaired")
PY

echo "== BUNDLE 11B REPAIR DONE =="
