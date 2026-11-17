# Path Analysis and Structural Equation Modeling

**Research brief [open] — feeds design addition #4, the flagged mathematical risk** (chained proportionality/correlation claims silently treated as exact proportionality: correlation coefficients multiplied as if they composed like constants). Grounding math: Sewall Wright's path analysis (1918–1934) and Structural Equation Modeling (SEM, Jöreskog 1970 onward). Written 2026-08-29. All claims source-verified; see Sources.

## What it is

- **Path analysis** = method for decomposing observed correlations among variables into components attributable to a *hypothesized causal structure*. Invented by Sewall Wright, geneticist, to reason about inheritance: introduced in 1918 ("On the nature of size factors," Genetics), applied to guinea-pig coat spotting in 1920 (PNAS), fully presented in 1921 ("Correlation and causation," Journal of Agricultural Research 20:557–585), formalized in 1934 ("The method of path coefficients," Annals of Mathematical Statistics 5:161–215).
- **Path diagram** = acyclic directed graph: nodes = variables, single-headed arrows = hypothesized causal (functional) influence, double-headed curved arrows = unanalyzed correlation (between exogenous variables or between error terms). Every endogenous node carries an **error term** (residual, `e`), the unexplained variance — Wright's diagrams always draw it; it is load-bearing, not decoration.
- **Path coefficient** = the weight on an arrow. In standardized form (all variables z-scored) it is the expected change in the child, in standard-deviation units, per 1-SD change in the parent *holding the other causes fixed*: for a linear model B = p_AB·A + e, `p_AB` is the standardized partial regression coefficient, and 1 − p²_AB is the share of variance explained by the error term. Unstandardized path coefficients are partial regression coefficients in raw units (Wright 1960 explicitly treats "path regressions" as alternative and complementary).
- What path analysis does: takes a *stated* causal diagram and derives what correlations the diagram predicts, or inverts observed correlations to estimate coefficients — and crucially, **splits an observed correlation into direct effect + indirect effect(s) + non-causal components** (common causes, selection). This is exactly the operation OpenVerifiers' flagged risk demands: OpenVerifiers wants to compose chained claims; Wright's machinery is the correct composition law, and it is *not* multiplication of correlations.
The flagged risk (design addition #4) names the failure precisely: silently multiplying correlation coefficients as exact proportionality constants. This brief's answer in one sentence: correlation coefficients are not proportionality constants at all — proportionality constants are path coefficients on declared functional edges — so the flag fires on *every* chain whose edges are correlational, and the only legitimate chain composition is Wright's tracing sum. Everything below is the verification of that sentence and its guardrail.


**Wright's own data.** The 1920 PNAS paper models piebald coat pattern in guinea pigs as determined by heredity and environment with quantified path coefficients. The 1921 paper's numerical illustrations use guinea-pig data on birth weight, litter size, and maternal weight, showing e.g. how maternal weight affects offspring birth weight both directly and indirectly through litter size — the canonical "decompose a correlation into direct + indirect" demonstration.

## Why correlation is not transitive

**The failure.** Let r_AB, r_BC, r_AC be pairwise Pearson correlations. In general:

```
r_AC  ≠  r_AB · r_BC
```

Three independent reasons:

1. **Constraints of correlation matrices (positive semidefiniteness).** For a 3×3 correlation matrix to be valid, r_AC must lie in a bounded interval:
   r_AC ∈ [ r_AB·r_BC − √((1−r_AB²)(1−r_BC²)),  r_AB·r_BC + √((1−r_AB²)(1−r_BC²)) ].
   Example: r_AB = r_BC = 0.9 forces r_AC ∈ [0.62, 1]; the naive product 0.81 is just *one* point in that interval, and nothing in the two pairwise correlations selects it. Products of correlations are not correlations and do not compose as exact constants.
2. **Colliders (the minimal concrete counterexample).** Let X, Y be independent unit-variance noises; set A = X, B = X + Y, C = Y. Then B = A + C — B is a common *effect* (collider) of A and C, and there is no causal chain A→B→C at all. Yet r_AB = r_BC = 1/√2 ≈ 0.707 and r_AC = 0. The chained product 0.707·0.707 = 0.5 ≠ 0. Two variables can both be strongly correlated with a third while being perfectly independent of each other. Pearson correlation is an association measure, not a path-composition operator.
3. **Confounding / spurious correlation.** If a variable H influences both B and C, then r_BC is inflated (or deflated) by the H-mediated component with no B→C link at all; any product built from such r's inherits the spurious part. This is the classical meaning of "correlation ≠ causation"; Langford, Schwertman & Owens (2001, The American Statistician 55:322–325) prove positive correlation is transitive only under restrictive conditions (essentially: degenerate/rank-deficient configurations), and Friedman (2015, The American Statistician, "Nontransitivity, Correlation, and Causation") extends the discussion.

**When chaining IS valid.** The product rule holds precisely when the objects multiplied are **path coefficients along a genuine causal chain with defined error terms**, not raw correlations. For the linear recursive system A→B→C, B = p_AB·A + e_B, C = p_BC·B + e_C, with A, e_B, e_C mutually uncorrelated (the Markov/stationarity conditions for linear systems: each error independent of its non-descendants):

```
r_AC = p_AB · p_BC        (and here r_AC = r_AB·r_BC because r_AB = p_AB, r_BC = p_BC)
```

The product rule survives. It breaks as soon as: errors are correlated, there is an unmeasured confounder touching any two variables, there is more than one path (the sum over paths rule takes over), or any edge is a mere observed correlation rather than a defined functional relation. Precisely: in Wright's formalism r_ij = Σ over all *open* paths of products of path coefficients, where a path is open iff it contains no collider — naive "correlation chaining" is exactly the mistake of treating every association path as open and every edge as a structural constant.

## Path analysis formalism

**Fundamental decomposition (Wright's first law).** For standardized variables, the correlation between any variable i and the outcome j decomposes over the direct causes (parents) k of i:

```
r_ij = Σ_k p_ik · r_kj   (k = parents of i, plus a spurious term when i and j share causes)
```

Recursively substituting the r_kj over parents' parents yields the tracing rule: **r_ij = sum, over all paths connecting i and j, of the product of the path coefficients along the path.** Wright's tracing rules (1934; restated in modern form by Pearl 2013):

1. Move along arrows in either direction, but stop at any node where the path would go forward (with an arrow) after having gone backward — at most one direction change; equivalently, do not pass through a collider (a node with two incoming arrows along the path).
2. Pass through each variable at most once (acyclic; no loops, no retracing).
3. Use each double-headed (correlation) arrow at most once per path.
4. Sum over all paths meeting the above; paths through colliders contribute zero.

**Effect decomposition.** For an exposure A and outcome C, the observed correlation r_AC = **direct effect** (coefficient on A→C if present) + **indirect effect(s)** (sum of products along mediated paths, e.g. p_AB·p_BC) + **spurious components** (paths that go through common causes). Total causal effect = direct + indirect only; spurious parts must be excluded for causal claims. Modern restatement: in a linear SEM the covariance matrix is generated as Φ = (I−B)⁻¹ Ψ (I−B)⁻ᵀ where B is the matrix of path coefficients among endogenous variables and Ψ the (possibly correlated) error covariance — the matrix form of the tracing rules (Bollen 1989; Pearl 2013).

**Unstandardized variant.** Path *regressions* (Wright 1960) use raw units; product rules then carry units and require care — only standardized coefficients compose as dimensionless products. A verifier multiplying unstandardized coefficients gets unit-laden nonsense unless units cancel explicitly.
**Worked example (the two chains that look alike).**

Chain A — *real causal chain, closed*: standardized system A = e_A, B = 0.8·A + e_B, C = 0.6·B + e_C, errors mutually uncorrelated, Var(A)=1. Solution: Var(B) = 0.64 + Var(e_B) ⇒ Var(e_B) = 0.36; standardized coefficients are p_AB = 0.8, p_BC = 0.6 (both endogenous variables already have unit variance by construction). Tracing: r_AB = p_AB = 0.8; r_BC = p_BC = 0.6; r_AC = p_AB·p_BC = 0.48 = r_AB·r_BC. Chaining *coincides with path product* — this is the one configuration where naive multiplication is numerically right, and it is right only because (i) edges are functional (they have defined mechanisms and residuals), (ii) errors are orthogonal, (iii) there is exactly one open path.

Chain B — *same numbers, spurious*: H is an unmeasured common cause, A = 0.8·H + e_A, C = 0.6·H + e_C, B = 0.8·A + 0.6·C + e_B (a collider at B), all unit-variance errors. Then r_AB and r_BC are inflated by the H-mediated components while r_AC is not the naive product — worst, a naive verifier would read "A correlates with B, B correlates with C" as evidence of the chain A→B→C when the true structure makes B the *joint effect* of A and C. The identical pair of correlations supports a chain in one reading and a collider in the other — only declared edge directions and error terms separate them.

This is why the guardrail's conditions are all *declarative* (edge kind, direction, error terms, confounding closure): the numbers cannot tell the verifier which chain it is holding.

## SEM

**Structural Equation Modeling** = path analysis + latent variables (Jöreskog 1970, "A general method for analysis of covariance structures," Biometrika 57:239–251; consolidated with measurement-model work of Keesling and Wiley into LISREL). Two coupled submodels:

- **Measurement model**: latent variables η, ξ are not observed; each is measured by multiple indicators via factor equations (x = Λx·ξ + δ, y = Λy·η + ε). This is confirmatory factor analysis.
- **Structural model**: regressions among latent variables (η = Bη + Γξ + ζ), the path-analysis core.
Latent variables are what let SEM compose chains *through unmeasured constructs*: e.g. "SES → reading ability → math achievement" with reading ability unobserved, identified only via indicator tests. Each indicator anchors the latent via a factor loading with its own error; the structural coefficients among latents are then estimated simultaneously with the loadings (full-information ML). For OpenVerifiers this is the formal precedent for composing chains whose internal nodes are *not directly evidenced* — the missing link is only compossible if the input context supplies measurement equations (indicators + loadings + errors) for it; otherwise the latent node is an Unknown, not a silent free parameter.

**Identification**: degrees of freedom = #(unique sample variances/covariances) − #(free parameters). A model is identified iff every parameter is a determined function of the population covariance matrix; under-identified models have infinitely many equally-fitting parameter sets. Correlations alone **never** identify causal direction: A→B and B→A with one edge each are covariance-equivalent, and many structurally different diagrams fit the same covariance matrix exactly ("equivalent models" problem; MacCallum, Wegener, Uchino & Fabrigar 1993). Identification is the formal answer to "can the verifier's evidence support this chain?" — same correlational evidence supports chains in both directions.
Identification arithmetic, minimal case: two measured variables A, C with one hypothesized edge A→C. Free parameters: 1 path coefficient + 1 error variance + Var(A) = 3; unique sample moments: Var(A), Var(C), cov(A,C) = 3; df = 0 — just-identified, any coefficient fits perfectly, so the data can neither confirm nor reject the chain. Add a measured mediator B (3 variables, chain A→B→C): parameters = 2 coefficients + 2 error variances + Var(A) = 5; moments = 6; df = 1 — one falsifiable constraint exists (the tracing-implied r_AC vs observed r_AC, an overidentifying restriction). A verifier asked to *certify* a chain from correlational input should reproduce exactly this df accounting: no overidentifying constraints ⇒ the chain is unfalsified-but-unconfirmed, which maps to `unverified_truth`, not `truth`.

**Estimation**: maximum likelihood on the covariance structure (minimize F_ML = log|Σ(θ)| + tr(S·Σ(θ)⁻¹) − log|S| − p), or least-squares/robust variants (WLS, DWLS, robust ML with Satorra–Bentler correction). **Goodness of fit**: χ² test of the model-implied vs observed covariance (non-significant = good fit in the classic logic), RMSEA, CFI/TLI, SRMR; fit never proves causality — it shows consistency with the data, and equivalent models fit equally.

**Software**: LISREL (Jöreskog & Sörbom, first SEM program, 1970s; Jöreskog & Sörbom 1993), AMOS (Arbuckle; IBM SPSS Amos), Mplus (Muthén & Muthén 1998–2017), lavaan (R; Rosseel 2012, JSS 48(2):1–36; free, active, the de facto modern standard), semopy (Python; Igolkina & Meshcheryakov 2020, Structural Equation Modeling 27(6):952–963, arXiv:1905.09376; active — PyPI latest 2.3.11 as of 2026-08), plus linWarper/OpenMx (R), pySEM (Python). For OpenVerifiers' stack (Python), semopy is the direct fit; lavaan is the reference implementation for cross-checking.

## OpenVerifiers takeaways

**(a) When is chained proportionality legitimate?** Rule for the grammar: multiplication of coefficients along a chain is a *defined operation* only when every edge is a **declared functional/causal relation** (a mapping with a defined mechanism, parameterized by a path coefficient with a specified error term) — never when an edge is a measured correlation. If the source material gives only correlations (statistical pipeline), correlations are *evidence for* a structure, not structure; the chain must be re-expressed as a path graph before any multiplication. This maps cleanly onto OpenVerifiers' ontology: edges between Fact nodes are Transformation/rule nodes whose `relation` is functional/causal; the statistical pipeline's outputs enter as evidence with confidence, not as proportionality constants. Grammar/TBox (domain knowledge) is where error terms and edge types are declared.

**(b) Correct composition = path-tracing/SEM logic, not exponentiation of correlations.** If a chain must be composed over correlation-like quantities, the verifier computes the *model-implied* correlation from the path graph: r_AC = Σ over open paths of Π coefficients (tracing rules above), equivalently Φ = (I−B)⁻¹Ψ(I−B)⁻ᵀ. Never r_AC := r_AB^k (exponentiating a shared coefficient as if the same relation repeated), never r_AC := Π r_i — unless the graph is a single open chain with uncorrelated errors (the one case where Π r_i coincides with the path product). Where the chain's arcs are only partially specified, mark the result with the Missing-paths flag (exists-unclosed-path), not silent completion.
Node-level recipe (maps the math onto the ontology): for target Fact node C and candidate chain A→…→C built from Transformation nodes, the verifier (1) materializes the subgraph of declared edges reachable from A and C; (2) enumerates simple paths from A to C and classifies each as open (no collider) or closed; (3) for every open path, multiplies the declared coefficients along it (each coefficient itself a typed attribute of its Transformation node, with confidence if estimated); (4) sums across paths. The result is the *model-implied correlation/effect*, a derived Fact whose `derivation` cites the path list and whose status is `derived` only if every coefficient is a declared mechanism — otherwise `derived` is refused and the node is `unverified_truth` with the reason from guardrail (d). A closed path (through a collider) contributes zero and is *not* an error: it is the correct Wright result, and the verifier should record it as such (it is how the collider counterexample A = X, B = X+Y, C = Y yields r_AC = 0).

**(c) Error/uncertainty propagation along paths** (feeds addition #5, first-class uncertainty): path products are differentiable functions of their coefficients; propagate intervals/confidences via standard formulas, e.g. for p = p_AB·p_BC:
```
var(p) ≈ p_BC²·var(p_AB) + p_AB²·var(p_BC) + 2·p_AB·p_BC·cov(p_AB, p_BC)
```
(trace marks crossing estimated links: every edge whose coefficient carries a confidence interval/standard error, i.e. came from the statistical pipeline rather than a declared mechanism, gets an `estimated` annotation; the trace records the propagation formula used). Multiply-through of intervals with unstated covariances is itself a risk: covariances between estimated coefficients are nonzero whenever they share data (e.g., two edges estimated from the same correlation matrix); silently treating them as independent narrows the interval falsely.

**(d) Guardrail — draft grammar rule (reject chains lacking defined error terms):**

```
RULE chain-composition (DRAFT)
A claim "A ∝ C via B" (chained proportionality) is composed as a path product
IFF all of:
  1. EDGE-KIND: every edge A→B, B→C is a declared functional/causal relation
     (mechanism + direction), NOT a measured correlation;
  2. ACYCLIC: the edge graph contains no cycle;
  3. ERRORS-DEFINED: every endogenous node declares an error term with
     defined orthogonality (uncorrelated with non-descendants) — a residual
     with an identifiability note, or explicit "no error" (deterministic edge);
  4. NO-UNMODELED-CONFOUNDER: no flagged unmeasured common cause between
     any adjacent pair (confounding closure declared per edge);
  5. MULTIPATH: if >1 open path exists, composition = SUM of path products
     (tracing), not a single product.
OTHERWISE: do NOT compute a numeric product. Emit an Unknown node
  status: unverified_truth, why-unknown: "correlation chaining without
  defined causal structure (missing error terms / direction / confounding
  closure); numeric composition not meaningful",
  evidence-would-resolve: [error specs for node B, causal direction
  declaration per edge, confounding closure per edge].
```

The default behavior is **refusal with a diagnostic Unknown**, which is precisely the "rather than computing garbage" behavior: a chain of three correlations has zero mathematically forced content beyond the PSD bounds, so any scalar it "derives" is fabricated. Note also the errors-DEFINED condition catches the silent-determinism mistake: chains with no declared residuals implicitly assert R² = 1 at every step.

**Two-source discipline.** All edge types, error specs, and causal directions come from the domain-knowledge source (TBox); all observed correlations/confidences come from the target/input-context source. A chain that needs an edge type present in neither source is unverifiable, not assumable.

## Conflicts / flags

- **Historical dispute over causal interpretation**: Niles (1922) criticized path analysis for over-reading causation from coefficients; Wright (1923, "The theory of path coefficients: A reply to Niles's criticism," Genetics 8:239–255) defended it. Resolution relevant to OpenVerifiers: path products are *only* as good as the declared diagram; the diagram is theory (TBox), never read off the data.
- **Correlation non-transitivity is often mis-stated**: some expositions say "r_AB = r_BC = r implies r_AC ≥ something" — the correct statement is the PSD bound above plus Langford et al.'s restrictive-conditions result. OpenVerifiers should treat ALL correlation chaining as suspect by default (guardrail above), not check a threshold.
- **r² chaining**: multiplying coefficients of determination ("A shares 40% variance with B, B shares 40% with C, so A shares 16% with C") is invalid — R² is not transitive and does not compose; any appearance in source material should carry the same flag.
- **Equivalent models / directionality**: covariance-equivalent structures mean the SAME correlational evidence supports opposite causation directions (A→B→C vs A→C←B with a collider, etc.). Error terms and declared mechanisms, not fit statistics, resolve which chain may be composed. SEM fit indices (RMSEA/CFI) never certify a diagram — at best they fail to falsify it.
- **Shared vocabulary with the Bayesian-net brief**: the collider/d-separation mechanics here (Pearl) are exactly the graphical criterion used to decide which chains are open in Bayes nets; the two formalisms agree on *which chains are invalid* and differ only in how they compose the valid ones (path products vs conditional-probability products) — see the companion brief on Bayesian networks.

## Sources

- Wright, S. (1918). On the nature of size factors. Genetics 3:367–374. https://academic.oup.com/genetics/article/3/4/367/5991517
- Wright, S. (1920). The relative importance of heredity and environment in determining the piebald pattern of guinea-pigs. PNAS 6(6):320–332. https://www.pnas.org/doi/10.1073/pnas.6.6.320
- Wright, S. (1921). Correlation and causation. Journal of Agricultural Research 20(7):557–585. https://www.scirp.org/reference/referencespapers?referenceid=1706123 (catalog entry; full text facsimiles widely archived)
- Wright, S. (1923). The theory of path coefficients: A reply to Niles's criticism. Genetics 8(3):239–255. https://academic.oup.com/genetics/article/8/3/239/6063849
- Wright, S. (1934). The method of path coefficients. Annals of Mathematical Statistics 5(3):161–215. https://doi.org/10.1214/aoms/1177732676 ; JSTOR: https://www.jstor.org/stable/2957502
- Wright, S. (1960). Path coefficients and path regressions: alternative or complementary concepts? Biometrics 16(2):189–202. https://www.jstor.org/stable/2527551
- Langford, E., Schwertman, N. C., & Owens, M. (2001). Is the property of being positively correlated transitive? The American Statistician 55(4):322–325. https://www.jstor.org/stable/2685695
- Friedman, E. M. (2015). Nontransitivity, correlation, and causation. The American Statistician 69(3). https://www.tandfonline.com/doi/full/10.1080/00031305.2015.1056382
- Pearl, J. (2013). Linear models: A useful "microscope" for causal analysis. Journal of Causal Inference 1(1):155–170. https://doi.org/10.1515/jci-2013-0003
- Pearl, J. (2009). Causality: Models, Reasoning, and Inference (2nd ed.). Cambridge University Press. https://www.cambridge.org/core/books/causality/
- Jöreskog, K. G. (1970). A general method for analysis of covariance structures. Biometrika 57(2):239–251. https://doi.org/10.1093/biomet/57.2.239
- Bollen, K. A. (1989). Structural Equations with Latent Variables. Wiley. https://onlinelibrary.wiley.com/doi/book/10.1002/9781118619179
- Kline, R. B. (2023). Principles and Practice of Structural Equation Modeling (5th ed.). Guilford Press. https://www.guilford.com/books/Principles-and-Practice-of-Structural-Equation-Modeling/Rex-Kline/9781462551910
- Jöreskog, K. G., & Sörbom, D. (1993). LISREL 8: Structural Equation Modeling with the SIMPLIS Command Language. Scientific Software International. https://www.ssicentral.com/
- Muthén, L. K., & Muthén, B. O. (1998–2017). Mplus User's Guide (8th ed.). https://www.statmodel.com/
- Rosseel, Y. (2012). lavaan: An R package for structural equation modeling. Journal of Statistical Software 48(2):1–36. https://www.jstatsoft.org/v48/i02 ; https://lavaan.ugent.be
- Igolkina, A. A., & Meshcheryakov, G. (2020). semopy: A Python package for structural equation modeling. Structural Equation Modeling: A Multidisciplinary Journal 27(6):952–963. arXiv: https://arxiv.org/abs/1905.09376 ; PyPI: https://pypi.org/project/semopy (latest 2.3.11 as of 2026-08)
- MacCallum, R. C., Wegener, D. T., Uchino, B. N., & Fabrigar, L. R. (1993). The problem of equivalent models in applications of covariance structure analysis. Psychological Bulletin 114(1):185–199. https://doi.org/10.1037/0033-2909.114.1.185
- Denis, D. J. (2006/2007). Origins of path analysis: Causal modeling and the origins of path analysis. Theory & Science 7(1). https://theoryandscience.icaap.org/content/vol7.1/denis.html
- Shipley, B. (2016). Cause and Correlation in Biology: A User's Guide to Path Analysis, Structural Equations and Causal Inference (2nd ed.). Cambridge University Press. https://www.cambridge.org/core/books/cause-and-correlation-in-biology/