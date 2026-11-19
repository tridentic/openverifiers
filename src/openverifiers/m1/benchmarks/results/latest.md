## Catch rate (invalid proofs rejected)

| domain | mutation | n | no_verification | mock_llm_judge | kernel | kernel right reason |
|---|---|---|---|---|---|---|
| math | unit_mismatch | 16 |   0.0% |   0.0% | 100.0% | 100.0% |
| math | sign_error | 12 |   0.0% |  41.7% | 100.0% | 100.0% |
| math | dropped_step | 11 |   0.0% |  63.6% | 100.0% | 100.0% |
| math | missing_precondition | 17 |   0.0% |   0.0% | 100.0% | 100.0% |
| math | wrong_effect | 12 |   0.0% |  41.7% | 100.0% | 100.0% |
| math | unreachable_target | 9 |   0.0% | 100.0% | 100.0% | 100.0% |
| math | duplicated_fact_id | 12 |   0.0% |  58.3% | 100.0% | 100.0% |
| math | circular_dependency | 7 |   0.0% |   0.0% | 100.0% | 100.0% |
| math | misread_given | 16 |   0.0% |  37.5% |  93.8% |  93.8% |
| **math** | **all** | 112 |   0.0% |  34.8% |  99.1% |  99.1% |
| code_requirements | unit_mismatch | 0 | n/a | n/a | n/a | n/a |
| code_requirements | sign_error | 0 | n/a | n/a | n/a | n/a |
| code_requirements | dropped_step | 4 |   0.0% |  50.0% | 100.0% | 100.0% |
| code_requirements | missing_precondition | 4 |   0.0% |   0.0% | 100.0% | 100.0% |
| code_requirements | wrong_effect | 4 |   0.0% |   0.0% | 100.0% | 100.0% |
| code_requirements | unreachable_target | 10 |   0.0% | 100.0% | 100.0% | 100.0% |
| code_requirements | duplicated_fact_id | 4 |   0.0% |  50.0% | 100.0% | 100.0% |
| code_requirements | circular_dependency | 2 |   0.0% |   0.0% | 100.0% | 100.0% |
| code_requirements | misread_given | 0 | n/a | n/a | n/a | n/a |
| **code_requirements** | **all** | 28 |   0.0% |  50.0% | 100.0% | 100.0% |

## False-rejection rate (valid proofs rejected)

| domain | n | no_verification | mock_llm_judge | kernel |
|---|---|---|---|---|
| math | 7 |   0.0% |   0.0% |   0.0% |
| code_requirements | 2 |   0.0% |   0.0% |   0.0% |

Kernel misses (mutants accepted): 1
- math_drop_speed~misread_given~0: given m 2 -> 4.0, rest recomputed consistently
Kernel false rejections: 0
Kernel rejections with an unexpected reason: 0
