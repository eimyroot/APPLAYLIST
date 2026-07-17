from __future__ import annotations

import ipaddress
import secrets
from dataclasses import dataclass


DESKTOP_PROTOCOL_VERSION = "applaylist-desktop-sidecar-v1"
SESSION_HEADER = "X-APPLAYLIST-Session"
PROCESS_NONCE_HEADER = "X-APPLAYLIST-Process-Nonce"


@dataclass(frozen=True, slots=True)
class SidecarSession:
    credential: str
    process_nonce: str

    @classmethod
    def generate(cls) -> "SidecarSession":
        return cls(
            credential=secrets.token_urlsafe(48),
            process_nonce=secrets.token_urlsafe(32),
        )

    def __post_init__(self) -> None:
        if not isinstance(self.credential, str) or len(self.credential) < 43:
            raise ValueError("sidecar credential must contain at least 256 bits of encoded entropy")
        if not isinstance(self.process_nonce, str) or len(self.process_nonce) < 32:
            raise ValueError("process nonce is too short")


@dataclass(frozen=True, slots=True)
class SidecarReadinessEnvelope:
    protocol_version: str
    process_nonce: str
    host: str
    port: int
    service_version: str
    ready_state: str

    def __post_init__(self) -> None:
        if self.protocol_version != DESKTOP_PROTOCOL_VERSION:
            raise ValueError("unsupported desktop sidecar protocol version")
        if not isinstance(self.process_nonce, str) or not self.process_nonce:
            raise ValueError("process nonce is required")
        try:
            address = ipaddress.ip_address(self.host)
        except ValueError as exc:
            raise ValueError("sidecar host must be a literal IP address") from exc
        if not address.is_loopback:
            raise ValueError("desktop sidecar must bind to loopback")
        if not isinstance(self.port, int) or isinstance(self.port, bool):
            raise TypeError("sidecar port must be an integer")
        if not 1 <= self.port <= 65535:
            raise ValueError("sidecar port must be between 1 and 65535")
        if not isinstance(self.service_version, str) or not self.service_version.strip():
            raise ValueError("service version is required")
        if self.ready_state not in {"starting", "ready", "degraded", "stopping"}:
            raise ValueError("invalid sidecar ready state")

    def validate_for_session(self, session: SidecarSession) -> None:
        if not secrets.compare_digest(self.process_nonce, session.process_nonce):
            raise ValueError("sidecar readiness nonce mismatch")

    def to_renderer_safe_dict(self) -> dict[str, object]:
        return {
            "protocol_version": self.protocol_version,
            "service_version": self.service_version,
            "ready_state": self.ready_state,
        }
