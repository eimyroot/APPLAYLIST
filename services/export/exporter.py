from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from core.config.settings import get_settings


class Exporter:
    def __init__(self) -> None:
        settings = get_settings()
        self.exports_dir = Path(settings.exports_dir)
        self.artifacts_dir = Path(settings.artifacts_dir)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def export_m3u(self, playlist_id: str, tracks: Iterable[object]) -> dict:
        tracks = list(tracks)

        m3u_path = self.exports_dir / f"{playlist_id}.m3u"
        manifest_path = self.artifacts_dir / f"{playlist_id}.manifest.json"
        warnings_path = self.artifacts_dir / f"{playlist_id}.warnings.json"
        audit_path = self.artifacts_dir / f"{playlist_id}.audit.json"

        resolved = []
        skipped = []
        warnings = []

        with m3u_path.open("w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for t in tracks:
                path = getattr(t, "path", None)
                title = getattr(t, "track_id", "unknown")

                if path:
                    f.write(f"#EXTINF:-1,{title}\n")
                    f.write(f"{path}\n")
                    resolved.append({"track_id": title, "path": path})
                else:
                    skipped.append({"track_id": title, "reason": "missing_path"})
                    warnings.append(f"Track {title} skipped: missing path")

        manifest = {
            "playlist_id": playlist_id,
            "track_count": len(tracks),
            "resolved_count": len(resolved),
            "skipped_count": len(skipped),
            "m3u_path": str(m3u_path),
        }

        audit = {
            "playlist_id": playlist_id,
            "resolved": resolved,
            "skipped": skipped,
        }

        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        warnings_path.write_text(json.dumps(warnings, indent=2, ensure_ascii=False), encoding="utf-8")
        audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

        return {
            "playlist_id": playlist_id,
            "m3u_path": str(m3u_path),
            "manifest_path": str(manifest_path),
            "warnings_path": str(warnings_path),
            "audit_path": str(audit_path),
            "resolved_count": len(resolved),
            "skipped_count": len(skipped),
        }
