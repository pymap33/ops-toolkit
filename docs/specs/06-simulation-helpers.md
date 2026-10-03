# Tool Spec — Shared Simulation Helpers

**Plan ref:** 0.6 · **Date:** 2026-10-02 · **Status:** approved 2026-10-02, building

This is a library module, not a calculator page. It has no UI of its own; its job is to be the one tested place where randomness lives, so the Monte Carlo tools (3.2 capex payback first) never hand-roll a sampler.

## 1. Problem

Every Monte Carlo tool needs the same four things: a reproducible random stream, a way to draw from an input range (triangular, PERT, ...), a way to summarize thousands of draws (P10/P50/P90, mean), and confidence that the sampler is actually drawing from the distribution it claims. Getting any of these subtly wrong gives plausible-looking, wrong risk numbers. This module builds them once and proves them against closed-form answers.

## 2. Who uses it

The toolkit's own tools (3.2 now; 3.1/3.3 if they are ever built). Not user-facing. Tool pages call it only through each tool's `compute_from_dict` entry point.

## 3. Inputs (the public API)

- **`make_rng(seed)`** → seeded `random.Random`. A tool always passes a seed (default fixed, user-changeable on the page), so the same inputs give the same output.
- **Distribution specs** — small frozen dataclasses with validation in `__post_init__`, each with `sample(rng)`, `mean`, `variance`, `ppf(p)` (inverse CDF), and `cdf(x)` where closed form exists:
  - `Uniform(low, high)`
  - `Triangular(low, mode, high)`
  - `PERT(low, mode, high, lam=4)` — the modified-PERT beta
  - `Normal(mean, sd)` with optional truncation `(lo, hi)` by rejection (cap on tries, raise if it cannot sample)
  - `LogNormal(mean, sd)` — parameterized by the **arithmetic** mean and sd of the variable itself (what a user means), converted internally to the underlying μ, σ
  - `Fixed(value)` — a degenerate input, so a tool can mix ranged and point inputs uniformly
- **`simulate(model, inputs, n, seed)`** — `inputs` is a dict of name → distribution; `model` is a function of a dict of drawn values returning a float. Returns the array of results, plus the drawn inputs (kept for the tornado/sensitivity step in 3.2). `n` default 10,000, max 200,000 (Pyodide time budget).
- **Summaries:** `percentile(xs, p)` (linear interpolation between order statistics, the same convention as NumPy's default, so it can be cross-checked), `summarize(xs)` → mean, sd, min, max, P10, P50, P90, plus `prob_below(xs, threshold)` / `prob_above` (e.g. "chance payback exceeds 4 years").

## 4. Outputs

Plain Python numbers and lists, JSON-serializable for the page bridge. No chart code here (the tornado chart is a 3.2 deliverable). Invalid input raises `ValueError` with a message naming the parameter.

## 5. Method

- **Sampling.** Uniform, normal and lognormal via the stdlib `random` methods. Triangular by inverse CDF from one uniform draw (not `random.triangular`, so `ppf` and `sample` share one formula and are tested together). PERT as a scaled beta: α = 1 + λ(m−a)/(b−a), β = 1 + λ(b−m)/(b−a), `rng.betavariate(α, β)` scaled to [a, b]. Degenerate PERT/triangular (low = mode = high) collapses to `Fixed`, not a divide-by-zero.
- **Stdlib only**, consistent with the rest of the repo (no NumPy dependency in Pyodide). `statistics.NormalDist` supplies the normal `ppf`/`cdf`; the regularized incomplete beta already written for `sample_size.py` is reused for the PERT `cdf`/`ppf` rather than duplicated (move it to a shared helper, keeping the sample-size tests green).
- **Sources for the analytic values** (read at the primary page before the tests are written, per the validation policy): Triangular and Uniform mean/variance — NIST/SEMATECH e-Handbook or a probability text; PERT / modified-PERT parameterization — Vose, or the standard beta-PERT references; lognormal moment conversion — NIST §1.3.6.6.9. The fetch tool returns summaries, so every number is recomputed by an independent standalone script before it goes in a test.

## 6. Validation

Expected values come from a standalone script (not from the implementation) and, where available, SciPy used for reference values only and never imported by the library.

| Property | Check | Pass tolerance |
|---|---|---|
| Moments | Sample mean and variance of 200,000 draws vs analytic, per distribution | within 4 standard errors (computed, not guessed) |
| Percentiles | Sample P10/P50/P90 vs analytic `ppf` | within 4 standard errors of a quantile |
| `ppf`/`cdf` | round trip `cdf(ppf(p)) = p` on a grid; `ppf` vs SciPy reference values | 1e-9 |
| Determinism | same seed → identical array; different seeds → different | exact |
| Independence | two inputs drawn in one `simulate` call have |sample correlation| < 4/√n | statistical |
| Composition | sum of normals: `simulate` result mean/sd vs analytic (μ₁+μ₂, √(σ₁²+σ₂²)) | 4 SE |
| `percentile` | vs NumPy's default method on fixed arrays, incl. n = 1, 2 and ties | exact to 1e-12 |
| Validation errors | every bad parameter (low > high, sd ≤ 0, mode outside range, λ ≤ 0, n > cap) raises | — |

Stochastic tests use fixed seeds so they cannot flake, and the tolerances are written in standard errors so a seed change would still pass in expectation.

## 7. Worked example

`Triangular(10, 12, 20)`: analytic mean 14.0, variance 4.6667 (sd 2.160), P50 = 20 − √(0.5·10·8) = 13.675. *(Corrected 2026-10-02: the first draft printed variance 6.2222 and P50 13.162, both wrong; caught by the independent SciPy reference script before any code was written.)* `PERT(10, 12, 20)`: mean (10 + 48 + 20)/6 = 13.0, variance (13−10)(20−13)/7 = 3.0. Same range: PERT variance 3.0 against 4.67 shows PERT is tighter than triangular, which is why 3.2 will default to it. Both appear in the tests as literal expected values.

## 8. Non-goals / when NOT to use

- **No correlation between inputs** in v1 (inputs are independent; the doc says so, because correlated cost drivers widen the true range). Rank-correlation (Iman–Conover) is a possible 0.6b.
- No Latin hypercube or quasi-random sampling in v1 (plain Monte Carlo; an LHS option is a later optimization if convergence is slow).
- No fitting distributions to data, no empirical/bootstrap sampler.
- No chart, no page, no tool-specific model. Not a substitute for judgment about the ranges: output is only as good as the input ranges, and results are scenario ranges, not forecasts.

## 9. Skill taught

Monte Carlo done honestly: seeded reproducibility, choosing a distribution for an expert-estimated range (triangular vs PERT), and testing a stochastic function against closed-form answers with error bars instead of eyeballing.

## 10. Definition of Done

- [ ] `opstoolkit/simulation.py` with the API above, type hints, stdlib only
- [ ] Expected values from a standalone script first; `tests/test_simulation.py` covers every row in section 6
- [ ] Incomplete-beta helper shared with `sample_size.py`; all prior 177 tests still green
- [ ] Runs under Pyodide in Node (smoke test) at the default `n` within a few seconds
- [ ] `docs/validation.md` and `docs/learning-log.md` (draft row for the user) updated
- [ ] `generate_manifest.py` run; `python -m pytest -q` green
- [ ] User approves before any push
