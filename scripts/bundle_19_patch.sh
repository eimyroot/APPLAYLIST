#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# ---- PATCH COMPOSER ----

COMPOSER_FILE="agents/playlist_composer/composer.py"

if [ ! -f "$COMPOSER_FILE" ]; then
  echo "Composer file not found: $COMPOSER_FILE"
  exit 1
fi

cp "$COMPOSER_FILE" "${COMPOSER_FILE}.bak"

cat > /tmp/composer_patch.py << 'PY'
from __future__ import annotations

from core.composer.intelligence_hook import intelligence_contribution

def apply_intelligence(score: float, track: dict, reasons: list):
    i_score, i_reasons = intelligence_contribution(track)

    if i_score > 0:
        score += i_score
        reasons.extend(i_reasons)

    return score, reasons
PY

# Inject import + hook usage (simple append strategy)
if ! grep -q "intelligence_contribution" "$COMPOSER_FILE"; then
  echo "Injecting intelligence integration..."

  echo "" >> "$COMPOSER_FILE"
  cat /tmp/composer_patch.py >> "$COMPOSER_FILE"
fi

echo "=== BUNDLE 19 PATCH DONE ==="
