# ov bench: 5 seed(s)

Verdict counts and pass/fail use seed 0; times use every seed.

| suite | cases | passed | verdicts | false_proven | false_refuted | unknown_answers | unknown_precision | unknown_recall | p50_s | p95_s | seed_varied_cases |
|---|---|---|---|---|---|---|---|---|---|---|---|
| adversarial | 5 | 5 | 4 | 0 | 0 | 2 | 1.0 | 1.0 | 0.0009 | 0.0028 | 0 |
| agentic | 5 | 4 | 7 | 0 | 0 | 1 | 1.0 | 1.0 | 0.0011 | 0.0022 | 0 |
| chemistry | 5 | 5 | 9 | 0 | 0 | 1 | 1.0 | 1.0 | 0.0542 | 0.104 | 0 |
| geometry | 5 | 5 | 9 | 0 | 0 | 0 |  |  | 0.0369 | 0.1572 | 0 |
| logic | 5 | 5 | 9 | 0 | 0 | 3 | 1.0 | 1.0 | 0.001 | 0.0017 | 0 |
| mathematics | 5 | 4 | 9 | 0 | 0 | 1 | 0.0 |  | 0.0011 | 0.0063 | 0 |
| physics | 6 | 5 | 6 | 0 | 0 | 2 | 1.0 | 1.0 | 0.002 | 0.0036 | 0 |
| all | 36 | 33 | 53 | 0 | 0 | 10 | 0.9 | 1.0 | 0.0017 | 0.1468 | 0 |

## Mismatches (seed 0)

- **agentic/deploy_checklist**: q2 missing: gold ['reviewed'], got ['assume']
- **mathematics/linear_system**: q1 verdict: gold PROVEN, got UNKNOWN; q1 values: gold ['7'], got None
- **physics/push_block**: q2 reason: gold missing_facts, got open_world; q2 missing: gold ['mu', 'normal_force'], got []
