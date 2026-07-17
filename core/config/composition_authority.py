from __future__ import annotations

import os
from enum import Enum


class CompositionAuthorityName(str, Enum):
    LEGACY = "legacy"
    CANONICAL = "canonical"


def resolve_composition_authority(
    value: CompositionAuthorityName | str | None = None,
) -> CompositionAuthorityName:
    raw = os.getenv("COMPOSITION_AUTHORITY", CompositionAuthorityName.LEGACY.value) if value is None else value
    if isinstance(raw, CompositionAuthorityName):
        return raw
    if not isinstance(raw, str):
        raise ValueError("COMPOSITION_AUTHORITY must be a string")
    normalized = raw.strip().casefold()
    try:
        return CompositionAuthorityName(normalized)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in CompositionAuthorityName)
        raise ValueError(
            f"Unsupported COMPOSITION_AUTHORITY: {raw!r}; allowed: {allowed}"
        ) from exc
