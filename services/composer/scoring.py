from core.harmonic import camelot_compatible
from services.integrations.spotify_client import SpotifyClient
from services.intelligence.fusion import fuse_signals


spotify = SpotifyClient()


def score_transition(a, b) -> float:
    score = 0.0

    if a.bpm and b.bpm:
        diff = abs(a.bpm - b.bpm)
        score += max(0, 1 - diff / 10)

    if camelot_compatible(a.camelot, b.camelot):
        score += 1.0

    if a.energy and b.energy:
        score += 1 - abs(a.energy - b.energy)

    # --- external intelligence ---
    external = spotify.get_audio_features(b.track_id)
    score += fuse_signals(b, external)

    return score
