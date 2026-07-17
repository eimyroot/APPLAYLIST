from __future__ import annotations

import re


_CAMELOT_RE = re.compile(r"^(?P<number>[1-9]|1[0-2])(?P<letter>[AB])$")


def normalize_camelot(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    return normalized if _CAMELOT_RE.fullmatch(normalized) else None


def camelot_compatible(
    left: str | None,
    right: str | None,
    *,
    allow_same: bool = True,
    allow_adjacent: bool = True,
    allow_relative: bool = True,
) -> bool:
    first = normalize_camelot(left)
    second = normalize_camelot(right)
    if first is None or second is None:
        return False

    first_number = int(first[:-1])
    second_number = int(second[:-1])
    first_letter = first[-1]
    second_letter = second[-1]

    if allow_same and first == second:
        return True

    if allow_relative and first_number == second_number and first_letter != second_letter:
        return True

    if allow_adjacent and first_letter == second_letter:
        clockwise = 1 if first_number == 12 else first_number + 1
        counterclockwise = 12 if first_number == 1 else first_number - 1
        return second_number in {clockwise, counterclockwise}

    return False
