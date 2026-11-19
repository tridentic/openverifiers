from pathlib import Path

#: Benchmark cases of the Milestone-1 verifier (moved under the m1 package).
M1_CASES = (Path(__file__).resolve().parents[2]
            / "src" / "openverifiers" / "m1" / "benchmarks" / "cases")
