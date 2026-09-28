# Tool Spec — Cost of Poor Quality (COPQ) Calculator

**Plan ref:** 1.1 · **Date:** 2026-09-27 · **Status:** draft — awaiting review

## 1. Problem

Quality and process-improvement projects stall at "what is it worth?" This tool turns scrap, rework, complaint and inspection activity into annual dollars, then prices a proposed improvement project: net annual savings, payback and NPV.

## 2. Who uses it

A quality engineer, process-improvement lead or operations/finance analyst building a savings case. They have annual volumes, unit costs and a rough idea of how much a project could reduce defects. They do not have a finance model.

## 3. Inputs

**A. Company context**

| Input | Unit | Rule |
|---|---|---|
| Annual revenue | $ | ≥ 0, optional. If blank or 0, "% of revenue" outputs are shown as n/a |

**B. Cost line items** — any number of rows, each assigned to one PAF category (Prevention, Appraisal, Internal failure, External failure). A row is entered in one of two modes:

| Mode | Fields | Annual cost |
|---|---|---|
| Direct | name, category, annual $ | the annual $ |
| Driver | name, category, units per year, cost per unit | units × cost per unit |

All values ≥ 0.

**C. Improvement project (optional)**

| Input | Unit | Rule |
|---|---|---|
| Reduction % per line item | % | 0–100, default 0. Applies to any category |
| One-time project cost | $ | ≥ 0 |
| Added annual prevention/appraisal spend | $/yr | ≥ 0, default 0 (the recurring cost of the fix) |
| Horizon | years | integer 1–10, default 3 |
| Discount rate | % | ≥ 0, default 10%. User-set assumption, shown on the page |

## 4. Outputs

- Annual cost by line item and by category, with each category's share of total cost of quality.
- **Total cost of quality (CoQ)** = Prevention + Appraisal + Internal failure + External failure.
- **Cost of good quality (CoGQ)** = Prevention + Appraisal. **Cost of poor quality (CoPQ)** = Internal failure + External failure.
- CoQ and CoPQ as % of revenue (when revenue is given).
- With a project: annual gross savings, net annual savings, post-project CoQ (and % of revenue), simple payback (months), NPV over the horizon, and a one-sentence decision statement.

**Decision statement (template):** "At these assumptions the project saves $X per year net, pays back in N months and has an NPV of $Y over H years at a Z% discount rate. Its result depends on the assumed reduction percentages: see the sensitivity table."

- **Sensitivity table:** NPV across a grid of reduction achieved (50%, 75%, 100% of the assumed reduction) against one-time project cost (−25%, base, +25%).

## 5. Method

- Line cost: direct = annual $; driver = units × unit cost.
- Category cost = sum of its line items. CoQ = sum of the four categories.
- Project gross savings = Σ (line cost × reduction %). Net annual savings = gross savings − added annual spend.
- Post-project CoQ = CoQ − gross savings + added annual spend.
- Payback (months) = one-time cost ÷ net annual savings × 12. If net savings ≤ 0, payback is "never".
- NPV = Σ over years 1..H of net annual savings ÷ (1 + r)^t, minus one-time cost. Savings are assumed to arrive at the end of each year and stay flat.

**Framework source:** the PAF (prevention–appraisal–failure) classification and the CoQ = CoGQ + CoPQ identity, per [ASQ, "What is Cost of Quality (COQ)?"](https://asq.org/quality-resources/cost-of-quality).

## 6. Validation

I found no published *numeric* worked example with a stated total that I could verify, so I am not claiming one. Validation is therefore in two parts, both documented in `docs/validation.md`:

1. **Definitional identities** (from the ASQ framework): CoQ = CoGQ + CoPQ; category shares sum to 100%; driver mode equals direct mode for the same annual $.
2. **Hand-computed reference case:** the worked example in § 7, computed independently of the library (a standalone script on 2026-09-27 produced the figures shown). Tests assert every output to the cent, and check payback and NPV against a closed-form annuity calculation.

**Open item:** find a published numeric example (an ASQ, Juran or textbook exercise) and add it as a third test. Until then the docs state plainly that validation is definitional plus hand-computed.

## 7. Worked example (synthetic)

Mid-size manufacturer, revenue $50,000,000.

| Line item | Category | Basis | Annual cost |
|---|---|---|---|
| Training | Prevention | direct | $60,000 |
| Process FMEA / QMS upkeep | Prevention | direct | $90,000 |
| Incoming inspection | Appraisal | direct | $120,000 |
| Final inspection | Appraisal | direct | $180,000 |
| Calibration | Appraisal | direct | $40,000 |
| Scrap | Internal failure | 12,000 units × $85 | $1,020,000 |
| Rework | Internal failure | 8,000 units × $30 | $240,000 |
| Customer returns | External failure | 900 units × $210 | $189,000 |
| Warranty | External failure | direct | $110,000 |

**Baseline:** Prevention $150,000; Appraisal $340,000; Internal failure $1,260,000; External failure $299,000. **CoQ $2,049,000 = 4.10% of revenue.** CoPQ $1,559,000 (76.1% of CoQ).

**Project:** scrap −40%, rework −50%, returns −30%, warranty −30%; one-time cost $250,000; added prevention $60,000/yr; 3-year horizon; 10% discount rate.

| Result | Value |
|---|---|
| Gross annual savings | $617,700 (scrap $408,000 + rework $120,000 + returns $56,700 + warranty $33,000) |
| Net annual savings | $557,700 |
| Post-project CoQ | $1,491,300 = 2.98% of revenue |
| Simple payback | 5.4 months |
| NPV (3 yr, 10%) | $1,136,917 |

**Decision:** approve. The project pays back inside six months. The sensitivity table shows whether it stays positive if only half of the assumed reduction is achieved.

## 8. Non-goals / when NOT to use this

- **No "hidden factory" multiplier.** Claims that visible failure cost is 5–10× larger are contested and not sourced here. Users may enter hidden costs as their own line items if they can defend them.
- **Not a costing system.** It does not measure defects. Garbage in, garbage out: the reduction percentages are assumptions, not predictions.
- **No revenue-loss modelling.** Lost customers and brand damage are not estimated unless entered as a line item.
- **Not for regulated-cost reporting.** Illustrative business-case tool only.
- Prevention/appraisal savings from the project (for example, less inspection) are supported only through the per-line reduction %, not modelled separately.

## 9. Skill taught

Turning operational quality data into a finance-grade savings case: line-item cost modelling, categorization by an established framework, and stating the sensitivity of a decision to its weakest assumption.

## 10. Definition of Done

- [ ] Spec approved
- [ ] Core library (`opstoolkit/copq.py`) implemented
- [ ] Tests pass, including definitional identities and the § 7 hand-computed case
- [ ] Browser page working, matches library output
- [ ] Worked example + "when not to use" on the page
- [ ] README table + hub page updated
- [ ] `docs/validation.md` updated (including the open published-example item)
- [ ] Deployed to Pages and checked live
- [ ] KB pointer/state updated
