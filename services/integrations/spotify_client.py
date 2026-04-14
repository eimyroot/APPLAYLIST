import random


class SpotifyClient:
    """
    Placeholder client (no auth yet)
    Returns simulated data for now.
    """

    def get_audio_features(self, track_id: str) -> dict:
        # TODO: real Spotify API integration
        return {
            "danceability": random.uniform(0.4, 0.9),
            "energy": random.uniform(0.3, 0.95),
            "valence": random.uniform(0.2, 0.9),
            "tempo": random.uniform(120, 135),
            "popularity": random.randint(10, 100),
        }
