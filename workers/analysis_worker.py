from __future__ import annotations

from services.analysis.analyzer import AudioAnalyzer


class AnalysisWorker:
    def __init__(self) -> None:
        self.analyzer = AudioAnalyzer()

    def process_file(self, track_id: str, path: str):
        return self.analyzer.analyze_file(track_id=track_id, path=path)
