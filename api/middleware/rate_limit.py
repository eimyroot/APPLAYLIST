from __future__ import annotations

import time
from collections import defaultdict, deque
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address
from typing import Deque, DefaultDict, Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


IPAddress = IPv4Address | IPv6Address
ProxyNetwork = IPv4Network | IPv6Network


def _parse_ip(value: str | None) -> IPAddress | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return ip_address(candidate)
    except ValueError:
        return None


def _is_trusted(address: IPAddress, networks: Iterable[ProxyNetwork]) -> bool:
    return any(address in network for network in networks)


def resolve_client_key(
    *,
    direct_peer: str | None,
    forwarded_for: str | None,
    trusted_proxy_depth: int,
    trusted_proxy_networks: tuple[ProxyNetwork, ...],
) -> str:
    """Resolve a stable rate-limit identity without trusting spoofable headers.

    The forwarded chain is used only when the direct peer and every configured
    trusted proxy hop belong to the explicit CIDR allowlist. Any malformed,
    incomplete or untrusted chain falls back to the direct peer.
    """
    direct_ip = _parse_ip(direct_peer)
    direct_key = str(direct_ip) if direct_ip is not None else (direct_peer or "unknown")

    if trusted_proxy_depth <= 0 or not trusted_proxy_networks:
        return direct_key

    if direct_ip is None or not _is_trusted(direct_ip, trusted_proxy_networks):
        return direct_key

    forwarded_values = [
        item.strip()
        for item in (forwarded_for or "").split(",")
        if item.strip()
    ]
    forwarded_ips = [_parse_ip(item) for item in forwarded_values]
    if not forwarded_ips or any(item is None for item in forwarded_ips):
        return direct_key

    chain = [item for item in forwarded_ips if item is not None] + [direct_ip]
    if len(chain) <= trusted_proxy_depth:
        return direct_key

    trusted_hops = chain[-trusted_proxy_depth:]
    if not all(_is_trusted(item, trusted_proxy_networks) for item in trusted_hops):
        return direct_key

    client = chain[-(trusted_proxy_depth + 1)]
    return str(client)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        limit_per_minute: int = 120,
        trusted_proxy_depth: int = 0,
        trusted_proxy_networks: tuple[ProxyNetwork, ...] = (),
    ) -> None:
        super().__init__(app)
        self.limit_per_minute = max(1, int(limit_per_minute))
        self.trusted_proxy_depth = max(0, int(trusted_proxy_depth))
        self.trusted_proxy_networks = trusted_proxy_networks
        self._hits: DefaultDict[str, Deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        direct_peer = request.client.host if request.client else None
        return resolve_client_key(
            direct_peer=direct_peer,
            forwarded_for=request.headers.get("x-forwarded-for"),
            trusted_proxy_depth=self.trusted_proxy_depth,
            trusted_proxy_networks=self.trusted_proxy_networks,
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        key = self._client_key(request)
        now = time.time()
        window_start = now - 60.0
        bucket = self._hits[key]

        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= self.limit_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "rate_limit_exceeded",
                    "limit_per_minute": self.limit_per_minute,
                },
            )

        bucket.append(now)
        return await call_next(request)
