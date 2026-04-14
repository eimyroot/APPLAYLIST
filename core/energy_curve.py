def target_energy(position: float) -> float:
    if position < 0.2:
        return 0.3
    elif position < 0.6:
        return 0.5
    elif position < 0.85:
        return 0.8
    else:
        return 0.4
