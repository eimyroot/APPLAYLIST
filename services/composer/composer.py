from __future__ import annotations

from core.energy_curve import target_energy
from data.models.playlist_candidate import PlaylistCandidate
from data.repositories.analysis_repository import AnalysisRepository
from services.composer.scoring import score_transition


class Composer:
    def __init__(self, repository: AnalysisRepository | None = None) -> None:
        self.repo = repository or AnalysisRepository()

    def compose(self, limit: int = 10) -> list[PlaylistCandidate]:
        tracks = self._load_tracks()
        if not tracks or limit <= 0:
            return []

        playlist = [tracks[0]]

        while len(playlist) < limit:
            current = playlist[-1]
            best = None
            best_score = -1.0

            for candidate in tracks:
                if candidate in playlist:
                    continue

                score = score_transition(current, candidate)

                position = len(playlist) / limit
                target = target_energy(position)

                if candidate.energy is not None:
                    score += 1 - abs(candidate.energy - target)

                if score > best_score:
                    best_score = score
                    best = candidate

            if best is None:
                break

            playlist.append(best)

        return playlist

    def _load_tracks(self) -> list[PlaylistCandidate]:
        return self.repo.list_playlist_candidates()
