from core.transition.tonal import TonalRelation, assess_tonal_relation


def test_missing_key_is_unknown_not_incompatible() -> None:
    result = assess_tonal_relation(None, "8A")
    assert result.relation is TonalRelation.UNKNOWN
    assert result.score == 50.0
    assert result.confidence == 0.0
    assert "PREVIEW_REQUIRED" in result.risk_codes


def test_missing_confidence_is_not_fabricated() -> None:
    result = assess_tonal_relation("8A", "8A")
    assert result.relation is TonalRelation.SAME_KEY
    assert result.confidence == 0.0
    assert "KEY_CONFIDENCE_UNAVAILABLE" in result.evidence_codes
    assert "PREVIEW_REQUIRED" in result.risk_codes


def test_same_and_adjacent_keys_score_high() -> None:
    same = assess_tonal_relation("8A", "8A", confidence_a=0.9, confidence_b=0.8)
    adjacent = assess_tonal_relation("8A", "9A", confidence_a=0.9, confidence_b=0.8)
    assert same.score > adjacent.score >= 85.0


def test_camelot_ring_wrap_is_adjacent() -> None:
    result = assess_tonal_relation("12A", "1A", confidence_a=1.0, confidence_b=1.0)
    assert result.relation is TonalRelation.ADJACENT


def test_distant_key_is_risk_not_rejection() -> None:
    result = assess_tonal_relation("8A", "2B", confidence_a=0.9, confidence_b=0.9)
    assert result.relation is TonalRelation.DISTANT
    assert result.score > 0.0
    assert "MELODIC_OVERLAP_RISK" in result.risk_codes

def test_tonal_relation_text_representation_remains_legacy_compatible() -> None:
    assert str(TonalRelation.SAME_KEY) == "TonalRelation.SAME_KEY"
