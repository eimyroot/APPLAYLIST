from __future__ import annotations


def resolve_context(index: int, total: int) -> str:
    if total <= 0:
        return "default"

    ratio = index / total

    if ratio < 0.3:
        return "warmup"
    elif ratio < 0.75:
        return "peak"
    else:
        return "closing"
