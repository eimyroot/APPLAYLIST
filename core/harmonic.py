from typing import Optional


def camelot_compatible(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b:
        return False

    try:
        num_a, mode_a = int(a[:-1]), a[-1]
        num_b, mode_b = int(b[:-1]), b[-1]
    except Exception:
        return False

    if a == b:
        return True

    if num_a == num_b and mode_a != mode_b:
        return True

    if mode_a == mode_b and (abs(num_a - num_b) == 1 or abs(num_a - num_b) == 11):
        return True

    return False
