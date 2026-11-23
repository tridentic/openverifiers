# ov bench: 1 seed(s) --strict

Verdict counts and pass/fail use seed 0; times use every seed.

| suite | cases | passed | verdicts | false_proven | false_refuted | unknown_answers | unknown_precision | unknown_recall | p50_s | p95_s | seed_varied_cases |
|---|---|---|---|---|---|---|---|---|---|---|---|
| adversarial | 50 | 50 | 42 | 0 | 0 | 15 | 1.0 | 1.0 | 0.001 | 0.003 | 0 |
| agentic | 22 | 22 | 28 | 0 | 0 | 2 | 1.0 | 1.0 | 0.0017 | 0.0032 | 0 |
| chemistry | 7 | 7 | 11 | 0 | 0 | 1 | 1.0 | 1.0 | 0.0395 | 0.0677 | 0 |
| geometry | 6 | 3 | 11 | 0 | 0 | 3 | 0.0 |  | 0.0227 | 0.1446 | 0 |
| logic | 7 | 7 | 12 | 0 | 0 | 4 | 1.0 | 1.0 | 0.0015 | 0.0021 | 0 |
| mathematics | 7 | 5 | 11 | 0 | 0 | 2 | 0.0 |  | 0.0024 | 0.0176 | 0 |
| physics | 8 | 7 | 8 | 0 | 0 | 2 | 1.0 | 1.0 | 0.0037 | 0.0062 | 0 |
| all | 107 | 101 | 123 | 0 | 0 | 29 | 0.828 | 1.0 | 0.0017 | 0.0399 | 0 |

## Mismatches (seed 0)

- **geometry/parallelogram_count**: q1 verdict: gold PROVEN, got UNKNOWN
- **geometry/rectangle_impossible**: q1 verdict: gold REFUTED, got UNKNOWN
- **geometry/square_fourth_vertex**: q2 verdict: gold PROVEN, got UNKNOWN
- **mathematics/cubic_vertex_none**: q1 verdict: gold REFUTED, got UNKNOWN
- **mathematics/linear_system**: q1 verdict: gold PROVEN, got UNKNOWN; q1 values: gold ['7'], got None
- **physics/push_block**: q2 reason: gold missing_facts, got open_world; q2 missing: gold ['mu', 'normal_force'], got []
