def fuse_signals(local, external):
    """
    Combine internal analysis + external signals
    """

    score = 0.0

    # BPM alignment
    if local.bpm and external.get("tempo"):
        diff = abs(local.bpm - external["tempo"])
        score += max(0, 1 - diff / 10)

    # Energy blend
    if local.energy and external.get("energy"):
        score += 1 - abs(local.energy - external["energy"])

    # Popularity boost
    if external.get("popularity"):
        score += external["popularity"] / 100

    # Danceability factor
    if external.get("danceability"):
        score += external["danceability"]

    return score
