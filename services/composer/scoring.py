from core.harmonic import camelot_compatible


def score_transition(a, b) -> float:
    score = 0.0

    if a.bpm and b.bpm:
        diff = abs(a.bpm - b.bpm)
        score += max(0, 1 - diff / 10)

    if camelot_compatible(a.camelot, b.camelot):
        score += 1.0

    if a.energy and b.energy:
        score += 1 - abs(a.energy - b.energy)

    return score
