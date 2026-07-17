from __future__ import annotations

from enum import Enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class CompositionAuthorityName(str, Enum):
    LEGACY = "legacy"
    CANONICAL = "canonical"


class CompositionAuthoritySettings(BaseSettings):
    composition_authority: CompositionAuthorityName = CompositionAuthorityName.LEGACY

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def resolve_composition_authority(
    value: CompositionAuthorityName | str | None = None,
) -> CompositionAuthorityName:
    if value is None:
        return CompositionAuthoritySettings().composition_authority
    if isinstance(value, CompositionAuthorityName):
        return value
    if not isinstance(value, str):
        raise ValueError("COMPOSITION_AUTHORITY must be a string")
    normalized = value.strip().casefold()
    try:
        return CompositionAuthorityName(normalized)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in CompositionAuthorityName)
        raise ValueError(
            f"Unsupported COMPOSITION_AUTHORITY: {value!r}; allowed: {allowed}"
        ) from exc
