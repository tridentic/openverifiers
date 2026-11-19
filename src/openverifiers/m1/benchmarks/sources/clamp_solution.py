def clamp(x, lo, hi):
    if lo > hi:
        raise ValueError("lo must not exceed hi")
    return min(max(x, lo), hi)
