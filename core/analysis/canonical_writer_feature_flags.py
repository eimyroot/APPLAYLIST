from __future__ import annotations

import os
from collections.abc import Mapping

_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "off", "disabled", ""}


def canonical_writer_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return whether the non-authoritative canonical writer is enabled.

    Missing, false-like, or invalid values fail closed to disabled.
    """

    source = os.environ if env is None else env
    value = source.get(
        "APPLAYLIST_CANONICAL_WRITER_ENABLED",
        "0",
    ).strip().lower()

    if value in _TRUE_VALUES:
        return True

    if value in _FALSE_VALUES:
        return False

    return False
