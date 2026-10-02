# Tool Spec — Sample-Size & Cost-of-Testing Planner

**Plan ref:** 2.1 · **Date:** 2026-10-01 · **Status:** approved 2026-10-01, built

## 1. Problem

Sample sizes are usually picked by habit ("30 per group") or copied from a table, with no view of what the test costs or what a missed real difference costs. This tool sizes a comparison test for a stated difference, variability, significance level and power, shows how power rises with n, and, when costs are supplied, finds the n that minimizes total cost (testing cost plus expected cost of missing a real effect) instead of assuming 80% or 90% power.

## 2. Who uses it

An engineer, quality or R&D analyst planning a comparison (new material vs. current, before vs. after a change, one lot vs. a spec). They know roughly how variable the measurement is, how big a difference matters, and what each test unit costs. They may know what missing a real improvement is worth.

## 3. Inputs

| Input | Unit | Rule |
|---|---|---|
| Test type | choice | One-sample / paired (difference from a target), or two independent samples with equal n |
| Difference to detect, δ | measurement units | > 0 |
| Standard deviation, σ | measurement units | > 0. For paired, the SD of the paired differences. A planning value, not a known truth |
| Significance level, α | — | 0.001–0.25, default 0.05 |
| Sides | choice | Two-sided (default) or one-sided |
| Target power | % | 50–99.9, default 80 |
| Fixed cost per study, F | $ | ≥ 0, optional |
| Cost per test unit, c | $ | ≥ 0, optional. Per unit measured; two-sample uses 2n units |
| Cost of missing a real effect, V | $ | ≥ 0, optional. What a real δ-sized difference is worth if the study fails to find it |
| Probability the effect is real, π | % | 1–100, default 50, used only with V |

## 4. Outputs

- **Required n** for the target power (per group for two-sample), rounded **up**, with the **actual power** at that n (like the Minitab report: actual ≥ target).
- **Power table** at a range of n around the answer, so the user sees the diminishing returns.
- **Sensitivity:** required n if σ is 20% larger, or δ is 20% smaller. Sample size scales with (σ/δ)², so small input errors move n a lot; the tool shows it.
- **Cost-of-testing tradeoff** (when c and V are given): total expected cost at each n = F + c × units + π × (1 − power) × V, the n that minimizes it, its power, and the saving against the target-power n.
- One-sentence decision statement.

## 5. Method

- Required n: smallest integer n whose **exact t-test power** meets the target. One-sample: df = n − 1, noncentrality λ = (δ/σ)√n. Two-sample (equal n): df = 2n − 2, λ = (δ/σ)√(n/2). Two-sided power = P(T′ > t_crit) + P(T′ < −t_crit) with T′ noncentral t. Starting guess from the normal formula n = (z₁₋α/2 + z₁₋β)² (σ/δ)², refined upward by the exact search. Source for the formulae and the t-iteration: [NIST/SEMATECH e-Handbook §7.2.2.2](https://www.itl.nist.gov/div898/handbook/prc/section2/prc222.htm).
- The noncentral-t CDF is computed in the standard library only (numerical integration over the chi-square variable), so the page runs in Pyodide with no SciPy. This is the main build risk and is validated independently (§ 6).
- Cost tradeoff: expected total cost as above, minimized by direct scan over n (power is monotone in n, cost is one-dimensional, so no closed form is needed). **The false-positive cost is left out on purpose:** at fixed α it is a constant and does not change the optimal n; α is an input.
- The cost-of-missing term is a judgment input, like the shortage cost in 2.3. The tool shows the full cost curve so the user can see how flat it is near the optimum.

## 6. Validation

1. **Minitab two-sample t example** (read at the source page; also reproduced independently by exact-power computation 2026-10-01): δ = 5, σ = 10, α = 0.05, power 0.90 → **n = 86 per group, actual power 0.903230**. Pass: n equal, actual power within 1e-5.
2. **NIST one-sample example** (source page: one-sided, α = 0.05, β = 0.10, δ = σ): normal formula (1.645 + 1.282)² = 8.567 → 9; the t-iteration (1.860 + 1.397)² = 10.6 → 11. Reproduced independently; exact t power also gives **n = 11**. The tool must return 11.
3. **NIST sample-size table: NOT yet verified.** The table values (e.g. 53 / 13 / 6 at α = β = 0.05 for δ = 0.5σ / 1σ / 1.5σ) agree with the normal-approximation formula to within 1, but are far below exact-t values at larger effects (exact-t gives 54 / 16 / 8 for that row). Until the table's own method is read at the source page, it is **not used as a pass/fail test**; § 6.2 stands in. Open item.
4. **Independent checks of the machinery:** the stdlib noncentral-t CDF against SciPy's across a grid of (df, λ, x) (SciPy used in a standalone check script only, never in the library); power monotone in n, δ and α; the n = ∞ limit equals the normal-formula n; the cost scan against a brute-force grid.
5. **Hand-computed reference case:** § 7, from a standalone script independent of the library, asserted to the dollar.

## 7. Worked example (synthetic)

Two-sample comparison of a new vs. current material. δ = 5, σ = 10 (d = 0.5), α = 0.05 two-sided. Fixed cost F = $2,000; $150 per unit tested (2n units); a real improvement missed is worth V = $200,000; π = 50%.

| n per group | Power | Testing cost | Expected missed-effect cost | Total |
|---|---|---|---|---|
| 40 | 59.8% | $14,000 | $40,185 | $54,185 |
| 64 (80% power) | 80.2% | $21,200 | $19,854 | $41,054 |
| 86 (90% power) | 90.3% | $27,800 | $9,677 | $37,477 |
| **89 (cost optimum)** | **91.3%** | $28,700 | $8,736 | **$37,436** |
| 120 | 97.1% | $38,000 | $2,889 | $40,889 |

(Values computed 2026-10-01 with SciPy as a reference; the build re-derives them from a standalone stdlib script and asserts to the dollar.)

**Decision:** test 89 per group. The common 80% power rule (n = 64) would cost about $3,600 more in expected terms; past about 90 per group each extra unit costs more than the missed-effect risk it removes. The optimum is flat (86 to 89 is under $50), which is the useful message: the exact V barely matters here, but it would matter if V were much smaller.

## 8. Non-goals / when NOT to use this

- **Means only in v1, normal data, equal group sizes.** No proportions (pass/fail), no unequal allocation, no non-parametric tests, no equivalence or non-inferiority tests. Proportions are the likely 2.1b; they need their own sourced examples.
- **No DOE planning in v1.** The plan row says "DOE", but factorial run counts, blocking and replication planning are a different tool with different sources. Logged as follow-up 2.1c.
- **σ is a planning guess.** Using a pilot-sample SD understates the needed n; the sensitivity rows show by how much, they do not fix it.
- **Power answers "will I detect a real δ-sized effect", not "is the effect important".**
- **V and π are judgments.** Treat the cost optimum as a range, not a point.
- Not a replacement for a statistician when the design is complicated (clustered, repeated, sequential).

## 9. Skill taught

Statistical power and what drives it ((σ/δ)² scaling, diminishing returns), and turning "how many samples" into a cost decision rather than a rule of thumb.

## 10. Definition of Done

- [x] Spec approved
- [x] Core library (`opstoolkit/sample_size.py`) implemented, stdlib only
- [x] Tests pass: Minitab example, NIST example, noncentral-t vs. SciPy grid, monotonicity, cost-scan vs. brute force, § 7 case
- [x] Browser page working, matches library output
- [x] Worked example + "when not to use" on the page
- [x] README table + hub page updated
- [x] `docs/validation.md` updated (including the open NIST-table item)
- [x] Deployed to Pages and checked live
- [x] KB pointer/state updated
