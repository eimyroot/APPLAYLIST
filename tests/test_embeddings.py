from data.models.analysis_record import AnalysisRecord
from data.repositories.analysis_repository import AnalysisRepository
from services.intelligence.embeddings import build_embedding, cosine_similarity
from services.intelligence.similarity import SimilarityService


def _record(track_id: str, bpm: float, energy: float, camelot: str) -> AnalysisRecord:
    return AnalysisRecord(
        track_id=track_id,
        analysis_version="0.1.0",
        features_version="0.1.0",
        extractor_backend="librosa",
        extractor_name="bundle-8-test",
        bpm=bpm,
        bpm_confidence=None,
        key=None,
        scale=None,
        camelot=camelot,
        energy=energy,
        loudness_db=None,
        duration_seconds=240.0,
        harmonic_ratio=0.4,
        percussive_ratio=0.6,
    )


def test_build_embedding_shape() -> None:
    rec = _record("t1", 128.0, 0.7, "8A")
    vec = build_embedding(rec)
    assert len(vec) == 6
    assert vec[0] > 0
    assert vec[1] == 0.7


def test_cosine_similarity_orders_related_tracks() -> None:
    repo = AnalysisRepository()

    repo.upsert(_record("source", 128.0, 0.70, "8A"))
    repo.upsert(_record("near", 129.0, 0.68, "8A"))
    repo.upsert(_record("far", 142.0, 0.20, "2B"))

    service = SimilarityService()
    results = service.find_similar("source", top_k=2)

    assert len(results) == 2
    assert results[0][0] == "near"
    assert results[0][1] >= results[1][1]


def test_cosine_similarity_value_range() -> None:
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    c = [0.0, 1.0, 0.0]

    assert round(cosine_similarity(a, b), 6) == 1.0
    assert round(cosine_similarity(a, c), 6) == 0.0
