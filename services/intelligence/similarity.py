from __future__ import annotations

from typing import List, Tuple

from data.connection import get_sqlite_connection
from data.models.analysis_record import AnalysisRecord
from services.intelligence.embeddings import build_embedding, cosine_similarity


class SimilarityService:
    def _load_records(self) -> List[AnalysisRecord]:
        with get_sqlite_connection() as conn:
            rows = conn.execute("SELECT * FROM analyses").fetchall()
        return [AnalysisRecord(**dict(r)) for r in rows]

    def find_similar(self, track_id: str, top_k: int = 5) -> List[Tuple[str, float]]:
        records = self._load_records()
        source = None
        for r in records:
            if r.track_id == track_id:
                source = r
                break

        if source is None:
            return []

        source_vec = build_embedding(source)
        scored: List[Tuple[str, float]] = []

        for candidate in records:
            if candidate.track_id == track_id:
                continue
            score = cosine_similarity(source_vec, build_embedding(candidate))
            scored.append((candidate.track_id, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]
