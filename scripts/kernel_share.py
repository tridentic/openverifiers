"""How many library theorems (src/openverifiers/packages, drafts excluded per D-025)
are PROVEN at {kernel} trust (MP §7 v1 exit criterion 4, MP §8 Trust).

    python scripts/kernel_share.py
"""

from __future__ import annotations

from pathlib import Path

from openverifiers.runner import run_file

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    total = kernel = 0
    for f in sorted((ROOT / "src/openverifiers/packages").rglob("*.ov")):
        res = run_file(f, files={str(f)})
        th = [a for a in res.classes if a.kind == "theorem"]
        total += len(th)
        kernel += sum(a.verdict == "PROVEN" and set(a.trust_base) == {"kernel"} for a in th)
    print(f"{kernel} / {total} library theorems at {{kernel}} ({100 * kernel // max(total, 1)}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
