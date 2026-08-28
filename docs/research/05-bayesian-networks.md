# Bayesian Networks for Correlated Fact Graphs

Status: **research input** — feeds additions #4 ("astronomical growth") and #5
(first-class uncertainty); siblings: `04-path-analysis-sem.md`, `03-dl-abox-tbox.md`.
Recommendation: full BN engine deferred past v1; the v1 obligation is
*negative* (never point-multiply correlations) plus a first-class
"estimatable" fact status carrying a distribution/interval.

---

## What it is

A Bayesian network (BN) is a pair $(G, \theta)$:

- $G$: a **directed acyclic graph** (DAG) over variables $X_1 \dots X_n$; an
  edge $X \rightarrow Y$ declares direct dependence of $Y$'s distribution on
  $X$.
- $\theta$: **conditional probability tables (CPTs)** — per variable $X_i$ a
  distribution $P(X_i \mid \text{Parents}(X_i))$, one row per parent-state
  combination.

The graph is a *declaration of conditional independences*, not a claim about
mechanism; variables with no connecting path (given conditioning) are declared
independent (Koller & Friedman, ch. 1–3).

Any joint respecting the DAG's independences factorizes via the **chain rule**

$$P(X_1, \dots, X_n) = \prod_{i=1}^{n} P(X_i \mid \text{Parents}(X_i)).$$

- **d-separation**: graphical criterion for $X \perp Y \mid Z$: a
  chain/fork through $M$ blocks when $M$ (or a descendant) is in $Z$; a
  collider blocks unless $M$ (or a descendant) is in $Z$ (conditioning on a
  collider *opens* it). Sound and complete for BNs (Koller & Friedman, ch.
  3.3).
- **Markov blanket**: minimal set shielding $X$ from the rest — parents,
  children, and co-parents (other parents of $X$'s children). Given it, $X$
  is independent of everything else (Koller & Friedman, ch. 3.3).
- **Factorization = independence structure**: with $k$ parents per node and
  binary variables, $O(n \cdot 2^k)$ parameters; the joint is the product of
  $n$ small tables — vs. $2^n$ entries for an explicit joint table.

## Factorization and why it is tractable

The "astronomical growth" problem (addition #4) is the naive representation: a
joint over $n$ correlated facts needs $2^n$ probabilities (binary case); a
*fully-connected correlation graph* (the loose layer as "everything correlated
with everything") needs $O(n^2)$ coefficients whose chaining explodes — the
number of simple paths between two nodes in a dense $n$-node graph is
exponential.

- **Parameter count**: $O(n \cdot 2^k)$ instead of $2^n$ or $O(n^2)$ pairwise
  entries ($k$ = max parent count); realistic domains keep $k \leq 4$–6 —
  sparsity makes the model writable, learnable, elicitable.
- **Path explosion**: a path through the graph is *not* a chain of
  point-multiplied correlations. The factorization computes the joint as one
  product over local CPTs; inference (below) reuses intermediate sums so the
  cost is governed by the graph's **treewidth**, not by path count.
- **Independence is stored once**, in the graph structure, instead of buried
  implicitly in a full table.

Precisely: representing/querying a sparse BN costs polynomial in $n 2^k$ and
exponential only in $k$ (treewidth, for inference); the dense representation is
exponential in $n$, point-chaining exponential in path length. That is the
entire justification for modeling the loose layer as a BN when it grows.

## Inference (exact and approximate)

- **Exact — variable elimination (VE)**: sum variables out one at a time,
  pushing sums inside the CPT product. Polynomial on trees/polytrees (Pearl
  1988); exponential in *induced width* otherwise.
- **Junction tree**: moralize + triangulate, cluster cliques, message pass on
  the tree. Exponential in *treewidth*; one-time triangulation pays off for
  repeated queries. Standard production engine (Hugin, Netica).
- **Belief propagation (sum–product)**: message passing on the network.
  Exact and polynomial on trees/polytrees (Pearl 1988); on loopy graphs an
  approximation with no guarantee (often converges well in practice).

**Approximate.** Sampling (forward sampling, likelihood weighting, Gibbs/MCMC;
loopy BP as special case) trades accuracy for speed — the workhorse on large
graphs.

**Complexity reality check.** Exact inference in *arbitrary* BNs is NP-hard
(Cooper 1990); guaranteed-error approximation is NP-hard too (Dagum & Luby
1993); structure learning likewise (Chickering 2002; Koller & Friedman, ch.
18). Tractable exactly when structured: polytrees (polynomial, Pearl 1988),
general graphs exponential in treewidth only. BNs win on *large structured*
graphs; any tractability claim must carry the sparsity/treewidth assumption.

## The causality caveat (edges ≠ causation; correlation still not transitive)

A BN encodes a *joint distribution*; edges describe dependence structure, not
mechanism (Koller & Friedman, ch. 1.2). Specifically:

- **Markov equivalence**: DAGs sharing skeleton and v-structures are
  indistinguishable from data — $X \rightarrow Y$ vs $X \leftarrow Y$ alone
  cannot be told apart; orientation is *not* evidence of cause.
- **Interventions**: $P(Y \mid X = x)$ vs $P(Y \mid do(X = x))$ differ under
  confounding; Pearl's do-calculus (Pearl, *Causality*, ch. 3) converts
  between them. An edge does not license "changing $X$ changes $Y$".
- **Non-transitivity persists**: factorization does not make correlation
  transitive. If $A$ and $C$ are independent causes of $B$ (fork
  $A \rightarrow B \leftarrow C$), $A$ correlates with $B$ and $B$ with $C$
  but $A \perp C$ — chain endpoints need not correlate; conditioning on the
  collider creates spurious dependence (Berkson's paradox class). A BN fixes
  the *cost* of correlated graphs, not the *fallacy* of chaining: propagation
  along chains is exact only under the factorization — wrong/loose edges →
  garbage in, exact garbage out.

For the verifier: BN edges are *statistical dependence structure*, never
causal proof, absent an interventional analysis (do-op, confounder control).

## Software

- **pgmpy** — pure-Python, MIT: `BayesianNetwork`, exact inference
  (VariableElimination, BeliefPropagation, junction tree) + do-calculus ops,
  approximate inference (likelihood weighting, Gibbs/MCMC), parameter and
  structure learning (PC, hill-climb). Closest fit for a Python verifier
  core. <https://pgmpy.org/> · <https://github.com/pgmpy/pgmpy>
- **bnlearn** — reference R package for structure/parameter learning
  (Scutari 2010; <https://www.bnlearn.com/>); same-named Python package
  (erdogant) mirrors a subset. Adds no inference capability pgmpy lacks.
  <https://erdogant.github.io/bnlearn/>
- **Netica** (Norsys) — commercial desktop tool with the fastest exact
  inference engines and a long record of deployed expert-elicited networks;
  good reference UX for elicitation (CPT entry, sensitivity analysis).
  <https://www.norsys.com/netica.html>
- **Hugin** — commercial suite, pioneer of the junction-tree algorithm;
  strong for large industrial models and decision graphs.
  <https://www.hugin.com/>

## OpenVerifiers takeaways

**(a) When the loose/statistical layer (addition #2) should be a BN rather
than a correlation graph.** Modeling choice, not default, with a threshold:

- Do NOT use a BN when the graph is tiny (≲ n=10 nodes, chain depth ≤ 3) or
  relationships are exact-functional (solver pipeline handles those; BN adds
  nothing).
- DO convert when: graph large or chains deep (n ≳ 10–20, depth > 3),
  relationships *probabilistic/estimated* rather than functional, and the
  query wants whole-graph uncertainty propagation. Rationale: dense is
  $O(n^2)$ and exponential-in-path; a BN with max indegree $k$ is $O(n 2^k)$,
  inference exponential only in treewidth.
- v1 needs no BN engine to honor the directive — only a *guard* refusing
  silent point-multiplication of correlations along chains (see (b)).

**(b) How uncertainty flows.** "probabilistic/estimated" is a first-class fact
status (addition #5) carrying a distribution/interval + confidence. Downstream
derived facts result from **composition of distributions, not point-multiplied
correlations**:

- Given CPTs $P(C \mid B)$, $P(B \mid A)$, a chain's conditional law is the
  convolution-style sum
  $$P(C=c \mid A=a) = \sum_{b} P(C=c \mid B=b)\, P(B=b \mid A=a)$$
  — marginalization over the intermediate node, exactly what variable
  elimination performs. Intervals propagate the same way: the sum over $b$
  carries the dependence — never independent per-edge interval widening.
- v1 rule: estimated link downstream of exact fact → estimated fact (status
  inheritance, confidence shrink); exact link downstream of estimated fact
  stays estimated. The derived value is the *posterior* given the evidence
  used — exactly BN inference; absent a BN engine, v1 must still compose
  distributions (sum/integrate over intermediate states), never multiply
  point estimates.

**(c) Trace must show the propagation path.** Per addition #5, the PROOF/PATH
object (addition #6) records edges crossed, variables marginalized out
(summation points), and estimated links — making "where did uncertainty enter
and how did it compound" auditable, matching BN query expressiveness (evidence
set, d-separation path) without shipping a BN engine.

**(d) BN vs SEM.** Both DAG-based, different questions (see
`04-path-analysis-sem.md`):

| | BN | SEM / path analysis |
|---|---|---|
| Content | CPTs; joint distribution | structural equations with explicit **error terms**, path coefficients |
| Direction | dependence structure (Markov-equivalence classes possible) | causal direction assumed per equation |
| Key query | $P(\text{query} \mid \text{evidence})$ (observational/conditional) | direct + indirect effect decomposition; interventional claims |
| Tractable on | large sparse graphs, bounded treewidth | small–medium causal path models |

Position: **SEM** for causal path claims with error terms ("chassis ∝ body ∝
car ∝ status" chains asserted as causal with coefficients); **BN** for
tractable joint inference and uncertainty propagation over large correlated
fact graphs. They coincide in the linear-Gaussian case (a linear SEM induces a
linear-Gaussian BN); BN do-calculus covers interventions. Causal claim → SEM;
big statistical claim → BN.

**(e) v1 adopt vs defer.**

Adopt in v1 (cheap, no BN engine):
1. "probabilistic/estimated" fact status carrying distribution/interval +
   confidence (finalized in addition #5).
2. Trace markers for crossing estimated links + marginalization points.
3. Guard: chains of loose/proportionality relationships are *never*
   point-multiplied; derivation must compose distributions or refuse.
4. Documentation rule: BN/SEM-style claims in the TBox carry an explicit
   "causal vs statistical" flag.

Defer (v2+):
1. Full BN inference engine (junction tree / variable elimination) — e.g.,
   pgmpy integration.
2. Structure learning from data (PC, hill-climb) — the verifier's structure
   comes from the TBox + target context, not from data mining.
3. Do-calculus / intervention analysis.
4. MCMC for approximate inference on huge graphs.

## Conflicts / flags

- **Tractability is conditional.** General BN inference is NP-hard (Cooper
  1990); guaranteed approximation NP-hard (Dagum & Luby 1993). Any
  tractability claim must cite sparsity/treewidth assumptions; "BN solves the
  astronomical growth" holds only for structured, sparse graphs.
- **Edge direction unidentifiable from data alone** (Markov equivalence);
  orientation must come from expert/TBox input — maps onto the verifier's
  two-source constraint (target context + domain knowledge).
- **Non-transitivity is a feature, not a bug** — the verifier must not let a
  BN *imply* correlation across a chain; only d-separation sanctions it.
- **Interval hazard**: independent per-edge interval arithmetic widens bounds
  and hides dependence; distributional composition (or flagged independence
  assumptions) mandatory.
- **Estimated-data caveat**: CPTs for estimated facts are themselves
  uncertain; v1 trace must show confidence shrink, preserving addition #5's
  invariant ("verified" never silently inherits from "estimated").

## Sources

- Koller & Friedman, *Probabilistic Graphical Models*, MIT Press, 2009 — ch.
  1–3, 9–10, 18. <https://mitpress.mit.edu/9780262013192/probabilistic-graphical-models/>
  · <https://pgm.stanford.edu/>
- Pearl, *Probabilistic Reasoning in Intelligent Systems*, Morgan Kaufmann,
  1988 — polytrees propagate in polynomial time. <https://www.sciencedirect.com/book/9780080514895/probabilistic-reasoning-in-intelligent-systems>
- Pearl, *Causality: Models, Reasoning, and Inference*, 2nd ed., CUP, 2009 —
  ch. 1–3: do-calculus, interventions, confounding. <https://bayes.cs.ucla.edu/BOOK-2K/>
- Pearl, Glymour, Jewell, *Causal Inference in Statistics: A Primer*, Wiley,
  2016. <https://bayes.cs.ucla.edu/PRIMER/>
- Cooper, "The Computational Complexity of Probabilistic Inference Using
  Bayesian Belief Networks", *AIJ* 42(2–3):393–405, 1990 — exact inference
  NP-hard. <https://doi.org/10.1016/0004-3702(90)90060-D>
- Dagum & Luby, "Approximating Probabilistic Inference in Bayesian Belief
  Networks Is NP-Hard", *AIJ* 60(1):141–153, 1993. <https://doi.org/10.1016/0004-3702(93)90036-B>
- Chickering, "Optimal Structure Identification with Greedy Search", *JMLR*
  3:507–554, 2002. <https://www.jmlr.org/papers/v3/chickering02b.html>
- Spirtes, Glymour, Scheines, *Causation, Prediction, and Search*, 2nd ed.,
  MIT Press, 2000 — constraint-based (PC) structure learning. <https://mitpress.mit.edu/9780262194402/causation-prediction-and-search/>
- Scutari, "Learning Bayesian Networks with the bnlearn R Package", *JSS*
  35(3), 2010. <https://arxiv.org/abs/0908.3817> · <https://www.bnlearn.com/>
- pgmpy — Python BN library. <https://pgmpy.org/> · <https://github.com/pgmpy/pgmpy>
- Netica (Norsys). <https://www.norsys.com/netica.html> · Hugin.
  <https://www.hugin.com/>
- Bollen, *Structural Equations with Latent Variables*, Wiley, 1989 — SEM
  error terms, path decomposition. <https://www.wiley.com/en-us/Structural+Equations+with+Latent+Variables-p-9780471011712>