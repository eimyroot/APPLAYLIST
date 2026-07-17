from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LibraryRootCapability:
    capability_id: str
    root_path: str
    issued_at: str
    session_id: str
    revoked: bool = False

    @classmethod
    def issue(cls, *, selected_root: str | Path, session_id: str) -> "LibraryRootCapability":
        root = Path(selected_root)
        if not root.is_absolute():
            raise ValueError("library root must be absolute")
        resolved = root.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("library root must be a directory")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id is required")
        return cls(
            capability_id=f"libcap_{secrets.token_urlsafe(24)}",
            root_path=str(resolved),
            issued_at=datetime.now(timezone.utc).isoformat(),
            session_id=session_id,
        )

    def authorize_scan(self, *, requested_root: str | Path, session_id: str) -> Path:
        if self.revoked:
            raise PermissionError("library capability is revoked")
        if not secrets.compare_digest(self.session_id, session_id):
            raise PermissionError("library capability belongs to another session")
        requested = Path(requested_root)
        if not requested.is_absolute():
            raise PermissionError("renderer-supplied relative paths are not authorized")
        resolved = requested.resolve(strict=True)
        allowed = Path(self.root_path)
        if resolved != allowed:
            raise PermissionError("requested root does not match the selected capability root")
        return resolved

    def to_renderer_safe_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "label": Path(self.root_path).name or "Selected library",
            "allowed_operations": ["bounded_scan", "read_track_summary"],
            "session_scoped": True,
            "revoked": self.revoked,
        }
