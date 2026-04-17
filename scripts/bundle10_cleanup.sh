#!/usr/bin/env bash
set -e

echo "=== BUNDLE 10 CLEANUP START ==="

# 1) remove iCloud garbage safely
echo "[iCloud cleanup]"
find . -name "*.icloud" -type f -print -delete || true

# 2) remove macOS junk
echo "[macOS junk cleanup]"
find . -name ".DS_Store" -delete || true

# 3) normalize weird duplicated files
echo "[normalize weird filenames]"
git ls-files | grep -E " 2\.md| 2\.py| 2\.json" || true

# 4) ensure .gitignore contains critical rules
echo "[update .gitignore]"
cat >> .gitignore << 'EOG'

# --- VOODOO CLEAN RULES ---
*.icloud
.DS_Store
*.log
*.tmp
*.bak
__pycache__/
*.pyc
.backup_*
data/cache/
data/tmp/
node_modules/
.env
EOG

# 5) stage only meaningful changes
echo "[git add selective]"
git add .gitignore || true
git add api/ || true
git add scripts/ || true
git add data/config/ || true

# DO NOT auto-add backups
git reset .backup_bundle11b/ || true

# 6) remove deleted tracked garbage
echo "[cleanup deleted]"
git add -u

echo "=== CLEANUP DONE ==="
