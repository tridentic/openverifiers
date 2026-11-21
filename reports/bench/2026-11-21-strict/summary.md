# ov bench: 1 seed(s) --strict

Verdict counts and pass/fail use seed 0; times use every seed.

| suite | cases | passed | verdicts | false_proven | false_refuted | unknown_answers | unknown_precision | unknown_recall | p50_s | p95_s | seed_varied_cases |
|---|---|---|---|---|---|---|---|---|---|---|---|
| adversarial | 5 | 5 | 4 | 0 | 0 | 2 | 1.0 | 1.0 | 0.001 | 0.059 | 0 |
| agentic | 5 | 4 | 7 | 0 | 0 | 1 | 1.0 | 1.0 | 0.0013 | 0.0021 | 0 |
| chemistry | 5 | 5 | 9 | 0 | 0 | 1 | 1.0 | 1.0 | 0.0547 | 0.0958 | 0 |
| geometry | 5 | 2 | 9 | 0 | 0 | 3 | 0.0 |  | 0.0365 | 0.1549 | 0 |
| logic | 5 | 5 | 9 | 0 | 0 | 3 | 1.0 | 1.0 | 0.0012 | 0.0019 | 0 |
| mathematics | 5 | 3 | 9 | 0 | 0 | 3 | 0.0 |  | 0.0014 | 0.0062 | 0 |
| physics | 6 | 5 | 6 | 0 | 0 | 2 | 1.0 | 1.0 | 0.0022 | 0.0033 | 0 |
| all | 36 | 29 | 53 | 0 | 0 | 15 | 0.6 | 1.0 | 0.0022 | 0.1169 | 0 |

## Mismatches (seed 0)

- **agentic/deploy_checklist**: q2 missing: gold ['reviewed'], got ['assume']
- **geometry/parallelogram_count**: q1 verdict: gold PROVEN, got UNKNOWN
- **geometry/rectangle_impossible**: q1 verdict: gold REFUTED, got UNKNOWN
- **geometry/square_fourth_vertex**: q2 verdict: gold PROVEN, got UNKNOWN
- **mathematics/am_gm_two**: q1 verdict: gold PROVEN, got UNKNOWN; theorem RealPair.am_gm: gold PROVEN, got UNKNOWN
- **mathematics/linear_system**: q1 verdict: gold PROVEN, got UNKNOWN; q1 values: gold ['7'], got None
- **physics/push_block**: q2 reason: gold missing_facts, got open_world; q2 missing: gold ['mu', 'normal_force'], got []
