# Tool Spec — Make-vs-Buy / Total Cost of Ownership (TCO) Model

**Plan ref:** 2.2 · **Date:** 2026-09-28 · **Status:** draft — awaiting review

## 1. Problem

"Make it or buy it?" is usually decided on unit price alone. That ignores fixed costs, one-time setup, quality losses, inventory carrying cost and supply risk, all of which move the answer. This tool compares two options on total annual cost, finds the volume at which the decision flips (the break-even volume), and shows how far the hidden costs shift it.

## 2. Who uses it

A procurement, operations or finance analyst deciding whether to bring a part or process in-house, outsource it, or switch between two ways of making it. They have a rough annual volume, the two options' prices and setup costs, and some estimates of quality and inventory effects.

## 3. Inputs

**Shared:** annual volume Q (units/yr, ≥ 0); horizon in years (integer 1–10, default 5) and discount rate (%, default 10%, a user-set assumption shown on the page), used only to annualize one-time costs.

**Per option (Option A = "Make", Option B = "Buy"; labels editable).** Both options take the same fields so the model is symmetric:

| Input | Unit | Rule |
|---|---|---|
| Fixed annual cost | $/yr | ≥ 0. Dedicated equipment, lease, staff, contract minimums |
| One-time cost | $ | ≥ 0. Tooling, qualification, transfer, switching |
| Variable cost per unit | $/unit | ≥ 0. Landed: material, labor, freight, duty |
| Defect rate | fraction of units | 0–1, default 0 |
| Cost per defect | $ | ≥ 0, default 0. Scrap, rework, returns handling. Can be taken from the COPQ tool |
| Inventory days held | days | ≥ 0, default 0. Average days of supply, including pipeline in transit and safety stock |
| Inventory carrying rate | % per year | ≥ 0, default 20%. A user-set assumption, shown on the page |
| Risk premium | % of variable cost | ≥ 0, default 0. Contingency for supply disruption, an explicit user assumption |

## 4. Outputs

- For each option: effective fixed cost per year, effective variable cost per unit, total annual cost at Q, and cost per unit at Q.
- **Preferred option** at Q, the dollar advantage per year, and the advantage as a % of the costlier option's total.
- **Break-even volume Q\*:** the volume at which the two options cost the same, and which option is cheaper above and below it. If there is no crossover, the tool says which option is cheaper at every volume and why.
- **Naive vs. TCO comparison:** the break-even and preferred option using only fixed cost and unit price, next to the full-TCO result, so the effect of the hidden costs is visible.
- **Cost-by-volume table:** total cost of each option at 50%, 75%, 100%, 125%, 150% and 200% of Q.
- **Sensitivity grid:** break-even volume against Buy variable cost (−20%, base, +20%) and Make variable cost (−20%, base, +20%).
- One-sentence decision statement.

**Decision statement (template):** "At Q units per year, [option] is cheaper by $X per year (Y%). The break-even volume is Z units: [Make] is cheaper above it and [Buy] below it. Ignoring quality, inventory and risk would have put the break-even at N units."

## 5. Method

- **Annualized one-time cost** = one-time × r ÷ (1 − (1 + r)^−n), the capital recovery factor. At r = 0 it is one-time ÷ n.
- **Effective fixed** F_eff = fixed + annualized one-time.
- **Effective variable** v_eff = v × (1 + risk + inventory days ÷ 365 × carrying rate) + defect rate × cost per defect.
- **Total annual cost** = F_eff + v_eff × Q. Each term is linear in Q, so the comparison is a straight-line break-even.
- **Break-even** Q\* = (F_eff,A − F_eff,B) ÷ (v_eff,B − v_eff,A).
  - Equal effective variable costs: no crossover. The option with the lower fixed cost is cheaper everywhere.
  - Q\* ≤ 0, or the higher-fixed option also has the higher variable cost: the other option dominates at every volume.
  - Otherwise the option with the higher fixed cost (and lower variable cost) is cheaper above Q\*.
- **Naive** uses F = fixed only and v = variable only.

**Framework source:** total-cost break-even for make-or-buy, per [*Fundamentals of Operations Management*, §4.10, eCampusOntario](https://ecampusontario.pressbooks.pub/fundamentalsopsmgmt/chapter/4-10-break-even-analysis-a-fundamental-tool-for-capacity-evaluation/): Q_BEP = FC ÷ (v_buy − v_make).

## 6. Validation

1. **Published textbook example (verified at the source, 2026-09-28).** The ABX Company example in the source above: Make fixed $160,000/yr, variable $100/unit; Buy fixed $0, variable $150/unit. Published results: break-even = 160,000 ÷ (150 − 100) = **3,200 units**; at 1,000 units, total cost of Make = 1,000 × 100 + 160,000 = **$260,000** and of Buy = 1,000 × 150 = **$150,000**, so Buy is preferred; Make is better above 3,200 units. The tool, with all TCO adders left at zero, must reproduce these exactly.
2. **Definitional / algebraic checks:** total cost at Q\* is equal for both options; the preferred option always has the lower total; the cost-by-volume table crosses at Q\*; swapping A and B swaps the result.
3. **Hand-computed TCO reference case:** § 7, computed by a standalone script independent of the library, asserted to the cent.

**Note on sources:** a web search summary suggested a second textbook example (70,000 units, $4,500 break-even). I could not find it on the cited page, so it is not used.

## 7. Worked example (synthetic, extends the ABX case)

Shared: Q = 3,500 units/yr, horizon 5 years, discount rate 10% (capital recovery factor 0.263797).

| | Make | Buy |
|---|---|---|
| Fixed annual | $160,000 | $0 |
| One-time (tooling / supplier qualification) | $90,000 | $30,000 |
| Variable per unit | $100 | $150 |
| Defect rate × cost per defect | 2% × $40 = $0.80 | 1% × $40 = $0.40 |
| Inventory days × carrying rate | 20 days × 20% | 45 days × 20% |
| Risk premium | 0% | 5% |

| Result | Make | Buy |
|---|---|---|
| Effective fixed | $183,742 | $7,914 |
| Effective variable / unit | $101.90 | $161.60 |
| Total annual cost at 3,500 units | $540,377 | $573,509 |

- **Preferred:** Make, by $33,132 per year (5.8% of Buy's total).
- **Break-even (full TCO):** 2,945 units. **Naive break-even:** 3,200 units.
- **What changed:** at 3,500 units the naive comparison shows Make ahead by $15,000 (Make $510,000 vs. Buy $525,000). Including the hidden costs more than doubles the advantage, and moves the break-even down by about 255 units, because Buy's longer pipeline and supply-risk premium add about $11.60 per unit, against $1.90 for Make. Make's larger annualized setup cost pulls the other way but does not offset it.

**Decision:** make in-house at this volume. The sensitivity grid shows how much Buy's landed price would have to fall to reverse that.

## 8. Non-goals / when NOT to use this

- **Two options only.** No multi-supplier or three-way comparison.
- **Linear costs.** No volume discounts, price breaks or step-fixed costs (a second machine at higher volume). Above the capacity of your single-machine assumption, the linear model will understate Make's cost.
- **Flat volume.** No demand growth or seasonality.
- **No taxes, FX or financing detail.** Pre-tax, single currency.
- **Strategic factors are not priced.** Intellectual property, core competence, supplier dependence and control are qualitative. The risk premium is a blunt stand-in.
- **The risk premium, carrying rate and defect costs are assumptions, not measurements.** The sensitivity grid exists to show how much they matter.

## 9. Skill taught

Total-cost thinking: turning a unit-price comparison into a fixed-plus-variable model, annualizing one-time costs, and showing how much of a sourcing decision is driven by costs that never appear on the quote.

## 10. Definition of Done

- [ ] Spec approved
- [ ] Core library (`opstoolkit/make_vs_buy.py`) implemented
- [ ] Tests pass, including the ABX published example, algebraic checks and the § 7 case
- [ ] Browser page working, matches library output
- [ ] Worked example + "when not to use" on the page
- [ ] README table + hub page updated
- [ ] `docs/validation.md` updated
- [ ] Deployed to Pages and checked live
- [ ] KB pointer/state updated
