from data.repositories.analysis_repository import AnalysisRepository
from services.composer.scoring import score_transition
from core.energy_curve import target_energy


class Composer:
    def __init__(self):
        self.repo = AnalysisRepository()

    def compose(self, limit: int = 10):
        tracks = self._load_tracks()
        if not tracks:
            return []

        playlist = [tracks[0]]

        while len(playlist) < limit:
            current = playlist[-1]
            best = None
            best_score = -1

            for candidate in tracks:
                if candidate in playlist:
                    continue

                s = score_transition(current, candidate)

                pos = len(playlist) / limit
                target = target_energy(pos)

                if candidate.energy:
                    s += 1 - abs(candidate.energy - target)

                if s > best_score:
                    best_score = s
                    best = candidate

            if best is None:
                break

            playlist.append(best)

        return playlist

    def _load_tracks(self):
        import sqlite3
        from data.connection import get_sqlite_connection

        with get_sqlite_connection() as conn:
            rows = conn.execute("SELECT * FROM analyses").fetchall()

        from data.models.analysis_record import AnalysisRecord
        return [AnalysisRecord(**dict(r)) for r in rows]
