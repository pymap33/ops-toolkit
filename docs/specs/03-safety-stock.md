# Tool Spec — Safety-Stock & Service-Level Cost Optimizer

**Plan ref:** 2.3 · **Date:** 2026-09-28 · **Status:** approved 2026-09-28

## 1. Problem

Safety stock is usually set by a rule of thumb ("95% service") with no view of what the last few points of service cost. This tool sizes the order quantity, safety stock and reorder point for an item with uncertain demand, shows what each service level costs to carry, and, when a cost per unit short is supplied, finds the service level that minimizes total cost instead of assuming one.

## 2. Who uses it

A planner, buyer, operations or finance analyst setting inventory policy for a purchased item. They know demand per period and how variable it is, the lead time, the ordering and holding costs, and (optionally) roughly what a shortage costs.

## 3. Inputs

| Input | Unit | Rule |
|---|---|---|
| Mean demand per period, d | units/period | > 0 |
| Std deviation of demand per period, σ_d | units/period | ≥ 0 |
| Lead time, L | periods (same unit as demand) | > 0. Constant, not variable in v1 |
| Periods per year, P | periods/yr | > 0, default 52. Annual demand D = d × P |
| Order cost, S | $/order | ≥ 0 (> 0 when Q is left blank, since EOQ needs it) |
| Holding cost, H | $/unit/yr | > 0. Usually unit cost × carrying rate. Zero would make EOQ and the optimum undefined |
| Order quantity, Q | units | Optional. Blank = use EOQ |
| Target cycle service level, CSL | % | 50–99.99, default 95 |
| Cost per unit short, p | $/unit | Optional, ≥ 0. Enables the optimal-service-level result. Shortages are assumed backordered |

## 4. Outputs

- **Lead-time demand:** mean μ_L = d × L and standard deviation σ_L = σ_d × √L.
- **At the target CSL:** z, safety stock SS = z × σ_L, reorder point ROP = μ_L + SS, annual carrying cost of safety stock = SS × H.
- **Order quantity and cost:** EOQ (or the entered Q), orders per year, annual ordering cost, annual cycle-stock holding cost, and **total annual inventory cost** = ordering + cycle-stock holding + safety-stock holding (+ expected stockout cost when p is given).
- **Service-level table** at CSL 80, 85, 90, 95, 97.5, 99, 99.5 and 99.9%: z, safety stock, annual carrying cost, the added cost of that step, expected units short per cycle, **fill rate**, and (with p) expected annual stockout cost and total cost.
- **Optimal service level** (when p is given): the CSL that minimizes safety-stock carrying plus stockout cost, its safety stock, and the annual saving against the target CSL.
- One-sentence decision statement.

**Fill rate ≠ CSL.** Cycle service level is the probability of no stockout in a cycle. Fill rate is the share of units delivered from stock. They differ a lot, so the table shows both.

## 5. Method

- σ_L = σ_d × √L; SS = z × σ_L with z = Φ⁻¹(CSL); ROP = μ_L + SS. Source: [*Fundamentals of Operations Management*, §8.7, eCampusOntario](https://ecampusontario.pressbooks.pub/fundamentalsopsmgmt/chapter/8-7-inventory-models-for-uncertain-demand/) (demand during lead time normally distributed).
- Q\* = √(2DS ÷ H); TC(Q) = S × D ÷ Q + H × Q ÷ 2. Source: [same book, §8.5](https://ecampusontario.pressbooks.pub/fundamentalsopsmgmt/chapter/8-5-inventory-models-for-certain-demand-economic-order-quantity-eoq-model/).
- Expected units short per cycle = σ_L × G(z), where G(z) = φ(z) − z × (1 − Φ(z)) is the standard normal loss function. Fill rate = 1 − σ_L × G(z) ÷ Q. Expected annual stockout cost = (D ÷ Q) × p × σ_L × G(z).
- Total annual cost = S × D ÷ Q + H × Q ÷ 2 + H × SS + stockout cost.
- **Optimal service level** (extension beyond the cited source): setting the derivative of H × σ_L × z + (D ÷ Q) × p × σ_L × G(z) with respect to z to zero gives Φ(z\*) = 1 − Q × H ÷ (p × D). If that ratio is ≤ 0.5, the tool sets z\* = 0 (no safety stock). This is the standard newsvendor-style critical-ratio result, but it is **not** in the cited textbook, so it is validated independently (§ 6, item 3) rather than by citation.
- Normal quantiles and the loss function use Python's standard library only.

## 6. Validation

1. **Published EOQ examples, verified at the source 2026-09-28** (arithmetic re-checked): Apple Canada, D = 250,000, S = $150, H = $12 → Q\* = 2,500, TC = $30,000, 100 orders/yr; BestBuy laptops, D = 1,500, S = $625, H = $130 → Q\* = 120.1, TC ≈ $15,612.5, 12.49 orders/yr; Modern Furniture, D = 45,000, S = $1,500, H = $0.70 → Q\* = 13,887.3, TC ≈ $9,721.11, 3.24 orders/yr.
2. **Published safety-stock example:** cell-phone kiosk, d = 20/week, σ_d = 4, L = 1 week, CSL = 90%. The book reports SS = 1.28 × 4 = 5.12 ≈ 5 (z rounded from a table). The tool uses the exact z = 1.2816, so SS = 5.126; the test accepts a match within 0.01 of the printed 5.12.
3. **Independent checks of the extension:** the loss function against numerical integration of the normal tail and known table values (G(0) = 0.3989, G(1) = 0.0833, G(2) = 0.0085); the closed-form optimal z against a dense brute-force grid search minimizing the total-cost function; fill rate and CSL identities.
4. **Hand-computed reference case:** § 7, from a standalone script independent of the library, asserted to the cent.

**Known error in the cited source, not reproduced.** The kiosk example prints the reorder point as "ROP = δ_L + SS = 4 + 5 = 9", using the *standard deviation* of lead-time demand where the formula on the same page calls for the *mean* (d_L = 20 × 1 = 20). With the mean, ROP = 20 + 5.1 ≈ 25. The tool follows the page's own formula (ROP = μ_L + SS), so it will not match that printed 9. This is documented in `docs/validation.md`.

## 7. Worked example (synthetic)

d = 200 units/week, σ_d = 40, L = 2 weeks, P = 52 (D = 10,400/yr), S = $75/order, H = $6/unit/yr, CSL target 95%, p = $25 per unit short, Q = EOQ.

| Result | Value |
|---|---|
| μ_L, σ_L | 400 units, 56.57 units |
| EOQ, orders per year | 509.9 units, 20.4 |
| Ordering + cycle-stock holding | $1,529.71 + $1,529.71 = $3,059.41 |
| At 95% CSL: z, SS, ROP | 1.6449, 93.05 units, 493.05 units |
| At 95%: safety-stock carrying, stockout cost, fill rate | $558.28, $602.65, 99.77% |
| **Optimal CSL** (critical ratio 0.98823) | **98.82%**: z\* = 2.2647, SS = 128.1 units |
| At the optimum: carrying + stockout cost | $768.65 + $117.07 = **$885.72** (vs. $1,160.93 at 95%) |
| Annual saving from the optimum vs. the 95% target | **$275.21** |

Service-level table (safety-stock carrying / expected stockout cost / total):

| CSL | z | SS | Carrying | Stockout | Total |
|---|---|---|---|---|---|
| 80% | 0.8416 | 47.6 | $285.66 | $3,220.12 | $3,505.78 |
| 90% | 1.2816 | 72.5 | $434.97 | $1,365.59 | $1,800.56 |
| 95% | 1.6449 | 93.1 | $558.28 | $602.65 | $1,160.93 |
| 99% | 2.3263 | 131.6 | $789.59 | $97.74 | $887.33 |
| 99.9% | 3.0902 | 174.8 | $1,048.86 | $7.99 | $1,056.85 |

**Decision:** hold about 128 units of safety stock (CSL ≈ 98.8%). Going lower saves carrying cost but adds more in shortages; going higher costs more than it saves. The answer depends on the $25 shortage cost, so the tool shows how the optimum moves with it.

## 8. Non-goals / when NOT to use this

- **Demand and lead time must be roughly normal and lead time constant.** Lumpy, intermittent or heavily skewed demand, and variable lead times, are outside v1. Planned follow-up 2.3b: lead-time variability, periodic review, lost sales.
- **Continuous-review (Q, R) policy only.** No periodic-review or min/max systems.
- **Shortages are backordered.** No lost-sales model.
- **No quantity discounts, no seasonality**, and holding cost is one number: obsolescence and spoilage are only as good as the H you enter.
- **The cost per unit short is the weakest input.** It is often a judgment. The table shows the full cost curve so you can see the range where the answer barely changes.
- Not a demand forecast. Garbage σ_d in, garbage safety stock out.

## 9. Skill taught

Turning a service-level target into a cost decision: the statistics of demand over lead time, the fact that each extra point of service costs more than the last, and finding the economic optimum instead of assuming one.

## 10. Definition of Done

- [ ] Spec approved
- [ ] Core library (`opstoolkit/safety_stock.py`) implemented
- [ ] Tests pass: EOQ published examples, kiosk safety-stock example, loss-function and grid-search checks, § 7 case
- [ ] Browser page working, matches library output
- [ ] Worked example + "when not to use" on the page
- [ ] README table + hub page updated
- [ ] `docs/validation.md` updated (including the source erratum)
- [ ] Deployed to Pages and checked live
- [ ] KB pointer/state updated
