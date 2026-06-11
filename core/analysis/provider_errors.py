from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ProviderErrorCode = Literal[
    "provider_unavailable",
    "provider_dependency_missing",
    "provider_runtime_error",
    "provider_output_invalid",
]


@dataclass(frozen=True)
class ProviderErrorDetails:
    code: ProviderErrorCode
    provider: str
    message: str
    recoverable: bool = True


class ProviderError(RuntimeError):
    def __init__(self, details: ProviderErrorDetails) -> None:
        self.details = details
        super().__init__(f"{details.code}: {details.provider}: {details.message}")


def provider_unavailable(provider: str, message: str) -> ProviderError:
    return ProviderError(
        ProviderErrorDetails(
            code="provider_unavailable",
            provider=provider,
            message=message,
            recoverable=True,
        )
    )


def provider_dependency_missing(provider: str, dependency: str) -> ProviderError:
    return ProviderError(
        ProviderErrorDetails(
            code="provider_dependency_missing",
            provider=provider,
            message=f"Missing optional dependency: {dependency}",
            recoverable=True,
        )
    )


def provider_runtime_error(provider: str, message: str) -> ProviderError:
    return ProviderError(
        ProviderErrorDetails(
            code="provider_runtime_error",
            provider=provider,
            message=message,
            recoverable=False,
        )
    )


def provider_output_invalid(provider: str, message: str) -> ProviderError:
    return ProviderError(
        ProviderErrorDetails(
            code="provider_output_invalid",
            provider=provider,
            message=message,
            recoverable=False,
        )
    )
