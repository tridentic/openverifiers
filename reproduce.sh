#!/usr/bin/env bash
# Regenerate every table of the v1 reports (MP-v1 exit 6). Run from the repo root
# in an environment with `pip install -e ".[dev]"`. Writes to repro-out/.
set -euo pipefail
OUT=${1:-repro-out}
mkdir -p "$OUT"
py=${PYTHON:-python}

echo "== trusted code (MP §8 Trust, D-030 caps)"
$py scripts/tcb_size.py | tee "$OUT/tcb.txt"

echo "== tests and coverage (raw, kernel, checker, state)"
$py -m coverage run -m pytest -q tests/v1 | tail -1 | tee "$OUT/tests_v1.txt"
$py -m coverage report | tail -1 | tee "$OUT/coverage.txt"
$py -m pytest -q | tail -1 | tee "$OUT/tests_all.txt"

echo "== benchmark suites (default and --strict)"
# ov bench exits 1 when a case fails: that is a finding, recorded in the table.
(ov bench --out "$OUT/bench" || true) | tail -1 | tee "$OUT/bench.txt"
(ov bench --strict --out "$OUT/bench-strict" || true) | tail -1 | tee "$OUT/bench_strict.txt"

echo "== JEE 2025 capability (default with drafts, and --strict)"
ov exam --drafts --json > "$OUT/exam.json" || true
ov exam --strict --json > "$OUT/exam_strict.json" || true
$py -c "import json,sys; [print(f, json.load(open(f))['summary']) for f in sys.argv[1:]]" \
  "$OUT/exam.json" "$OUT/exam_strict.json" | tee "$OUT/exam.txt"

echo "== differential testing (5,000 cases, seed 0)"
$py -m openverifiers.bench.differential --cases 5000 --seed 0 > "$OUT/differential.json"
$py -c "import json; d=json.load(open('$OUT/differential.json')); print({k: d[k] for k in ('agree','refused','disagree')}, d['exp_derivatives']['disagree'])" | tee "$OUT/differential.txt"

echo "== unsound mutants: rule path and object path (Condition B)"
($py -m pytest -q tests/v1/test_checker.py tests/v1/test_object_mutants.py -s || true) \
  | grep -E "\{'|killed|passed|failed" | tee "$OUT/mutants.txt"   # per-path tallies

echo "== library theorems at {kernel} (MP §8 Trust)"
$py scripts/kernel_share.py | tee "$OUT/kernel_share.txt"

echo "== timing limits (MP §8 Performance: ov check p95, q11, 10k facts)"
($py -m pytest -q -m bench || true) | tail -1 | tee "$OUT/timing.txt"

echo "== faithfulness lint"
($py -m openverifiers.bench.faithfulness || true) | tail -1 | tee "$OUT/faithfulness.txt"

echo "== gold and meaning gates over the whole history"
PYTHONPATH=src $py -m openverifiers.bench.gold_gate "$(git rev-list --max-parents=0 HEAD | tail -1)" HEAD \
  | tee "$OUT/gold_gate.txt" || true     # every line: one per violation

echo "repro: done; tables in $OUT/"
