from __future__ import annotations

from services.structure.structure import StructureAnalyzer


class StructureWorker:
    def __init__(self) -> None:
        self.analyzer = StructureAnalyzer()

    def process_file(self, path: str):
        return self.analyzer.analyze_file(path)
