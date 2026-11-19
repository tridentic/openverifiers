import re

_PART = re.compile(r"(\d+)([hms])")
_SCALE = {"h": 3600, "m": 60, "s": 1}


def parse_duration(text):
    if not isinstance(text, str) or not text:
        raise ValueError("empty duration")
    pos, total, last = 0, 0, -1
    for m in _PART.finditer(text):
        if m.start() != pos:
            raise ValueError(f"unexpected text at {pos}")
        rank = "hms".index(m.group(2))
        if rank <= last:
            raise ValueError("units must appear once, in h, m, s order")
        last, pos = rank, m.end()
        total += int(m.group(1)) * _SCALE[m.group(2)]
    if pos != len(text):
        raise ValueError(f"unexpected text at {pos}")
    return total
