from services.composition.camelot import camelot_compatible, normalize_camelot


def test_normalize_camelot_accepts_valid_case_and_spacing() -> None:
    assert normalize_camelot(" 8a ") == "8A"
    assert normalize_camelot("12B") == "12B"


def test_normalize_camelot_rejects_invalid_values() -> None:
    assert normalize_camelot(None) is None
    assert normalize_camelot("") is None
    assert normalize_camelot("0A") is None
    assert normalize_camelot("13B") is None
    assert normalize_camelot("C#m") is None


def test_camelot_supports_same_adjacent_relative_and_wraparound() -> None:
    assert camelot_compatible("8A", "8A")
    assert camelot_compatible("8A", "9A")
    assert camelot_compatible("1A", "12A")
    assert camelot_compatible("8A", "8B")


def test_camelot_respects_disabled_rules_and_invalid_keys() -> None:
    assert not camelot_compatible("8A", "8A", allow_same=False)
    assert not camelot_compatible("8A", "9A", allow_adjacent=False)
    assert not camelot_compatible("8A", "8B", allow_relative=False)
    assert not camelot_compatible("8A", "10A")
    assert not camelot_compatible("invalid", "8A")
