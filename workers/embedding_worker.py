from __future__ import annotations

from services.intelligence.similarity import SimilarityService


class EmbeddingWorker:
    def __init__(self) -> None:
        self.similarity = SimilarityService()

    def find_neighbors(self, track_id: str, top_k: int = 5):
        return self.similarity.find_similar(track_id=track_id, top_k=top_k)
