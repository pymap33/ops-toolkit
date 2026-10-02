# Tool Spec — Process-Chain Should-Cost Builder

**Plan ref:** 3.6 · **Date:** 2026-10-01 (revised same day after the user's scope input) · **Status:** approved 2026-10-01, built

**Revision note.** First drafted as a flexible-film-only tool. The user pointed out that extruders, laminators and pouch formers sit in different parts of the value stream and are sometimes one company and sometimes several, and that **rough estimation is the honest standard**. So: the engine is **generic over an ordered chain of process steps**, each step can be flagged as a hand-off to a **separate company** (so vertical integration versus separate stages, and the margin stacking between them, is modeled), and results are shown as a **bounding range**, not a point. Flexible packaging is the worked example, not a hard-coded assumption.

## 1. Problem

A buyer of a converted, multi-step product (for example a printed, laminated pouch) is handed a quote and has no view of what it *should* cost: how much is material, how much is conversion, how much is waste, tooling, overhead and margin, and how much of the price is margin stacked across separate companies. This tool builds the price bottom-up from the material structure and the process chain, shows a plausible range, and compares it with a quote, so the conversation moves from "your price is high" to "here is where the gap could be".

## 2. Who uses it

A packaging engineer, buyer or cost analyst preparing for a supplier negotiation, a make/outsource decision, or a supply-chain question ("what do we gain by buying film and laminating ourselves?"). They know the structure and geometry and can estimate machine rates and speeds from experience or public sources. The tool takes **all prices and rates as user input**, ships no market data (commodity indices are paywalled and go stale) and uses no employer data.

## 3. Inputs

**Materials (any number):** name · gsm (g/m²) **or** thickness (µm) × density (g/cm³) · price ($/kg or $/lb) · **enters at** which step (resin at extrusion, ink at print, adhesive at lamination).

**Format:** web width (m) · pouches (or units) per web metre = lanes ÷ repeat length (the user enters lanes and repeat, or units per metre directly). One web width is used for the whole chain (v1 simplification).

**Process steps (an ordered list; any number; any process — extrusion, print, laminate, slit, pouch-make, fill):**
name · machine rate ($/hr, all-in) · **speed**, in either **m/min** (web-speed steps) or **kg/hr** (throughput steps such as extrusion) · setup time (hr) · setup waste (m of web) · run yield (%) · **hand-off after this step to a separate company?** (yes/no).

**Economics:** overhead (% on the stage's own material, conversion and bought-in input) · margin (% of the stage's selling price) — applied at every step flagged as a hand-off and always at the last step. Optional per-step overrides, since different companies carry different overhead and margin. Tooling cost ($) and amortization quantity (units).

**Order:** good units required.

**Uncertainty band (for the range):** one percentage for prices and rates (default ±15%), speeds (default ±15%), and run yield (default ±2 points).

**Optional:** quoted price per 1,000, to compare.

## 4. Outputs

- **Should-cost price per 1,000 units** (base case) and the breakdown: material (by layer), conversion (by step), cost of waste, tooling, overhead, margin.
- **A bounding range:** low = every price and rate at its favorable end, speeds and yields favorable; high = all unfavorable. **This is an outer bound, not a confidence interval** (all inputs landing at one extreme together is unlikely) and the page says so.
- **Margin stacking:** price and margin dollars by stage, so a chain of three separate companies can be compared with the same chain in one plant.
- **Cost of waste** as its own line: cost at the modeled yields and setup waste minus cost at perfect yield and no setup waste.
- **Quote comparison** (if a quote is entered): where it falls relative to the range (below / inside / above), the gap in $ and %, and the margin it implies at the base cost.
- **Sensitivity:** change in price per 1,000 for material prices +10%, machine rates +10%, speeds −10%, run yields −2 points, order quantity halved.
- One-sentence decision statement.

## 5. Method

- **Material weight:** gsm = thickness (µm) × density (g/cm³) (dimensionally g/m²). Cost per m² = gsm × price ÷ 1,000 (price in $/kg).
- **Yield identity (for lb/MSI views):** film yield (in²/lb) = 27,680 ÷ (mils × specific gravity), from 1 lb of water = 27.68 in³.
- **Flow, backwards from the good output.** Required output length of the last step O = units ÷ units per web metre. For each step, last to first: input length I = O ÷ run yield + setup waste, and that I is the previous step's required output. Yields compound multiplicatively (0.98 × 0.99 × 0.96 = 0.9314, not 0.93).
- **Material cost** at step k = I_k × web width × gsm × price, for each material that enters at step k.
- **Conversion cost** at step k: m/min steps, hours = setup + I_k ÷ speed ÷ 60; kg/hr steps, hours = setup + (mass processed) ÷ speed, with mass = I_k × width × cumulative gsm of the materials entered at or before step k. Cost = hours × rate. (Boothroyd Dewhurst: cost per unit = hourly rate ÷ line speed.)
- **Chain with hand-offs.** Let T₀ = 0 and, for each step k, base_k = T_(k−1) + M_k + C_k. At a hand-off step (and always the last step), T_k = (base_k × (1 + overhead) + tooling_k) ÷ (1 − margin), where tooling applies at the last step only. At a non-hand-off step, T_k = base_k (inside one company the cost passes through and overhead and margin are taken once, at the end). The price is T_last. Overhead at a downstream stage applies to what it receives as well as what it adds; this compounding is a deliberate simplification and the page says so.
- **Tooling:** tooling cost ÷ amortization quantity × order quantity.
- **Range:** re-run the model with the uncertainty band applied in the favorable and unfavorable directions.
- **Structure sources:** [BN Pack, *How to Calculate Film Yield and Packaging Cost per Unit*, 2026-08-19](https://pouchespack.com/how-to-calculate-film-yield-and-packaging-cost-per-unit/) (lanes, repeat, roll yield, waste waterfall); [DFMA / Boothroyd Dewhurst, *Plastic Extrusion Cost Estimating*, Mar 2026](https://www.dfma.com/resources/plastic-extrusion-cost.asp) (resin + die amortization + line rate ÷ speed + secondary ops).
- Standard library only.

## 6. Validation

**Stated plainly: no authoritative published end-to-end should-cost with a known quoted price was found.** The two published worked examples are vendor web pages, one with an error. Validation is therefore *structural and arithmetic*, which matches the tool's stated purpose (rough estimation), and the tool and page say so.

1. **BN Pack worked example** (read at the primary page and arithmetic re-checked 2026-10-01): 0.96 m web, 4 lanes, 0.20 m repeat, 2,500 m roll → (2,500 ÷ 0.20) × 4 = 50,000 theoretical pouches; at 94% yield 47,000 good; roll cost $4,230 → $0.09 per good pouch; + $0.004 tooling + $0.001 testing + $0.002 quality loss → $0.097. The 3-lane variant gives 37,500 theoretical. The tool must reproduce each figure. **Caveat:** the page's waterfall computes 93.14% but its example then uses 94%; the test uses the 94% the example states.
2. **DFMA extrusion example, structure only.** Die amortization $8,000 ÷ 2,000,000 ft = $0.004/ft and processing $80/hr ÷ (50 ft/min × 60) = $0.027/ft reproduce. **Known error in the source, not reproduced:** the weight step reads "0.75 in² × 12 in/ft × 1.4 g/cc ÷ 16.387 ≈ 0.77 lb/ft", which has a unit error; for 0.75 in² the correct value is 0.75 × 12 × 16.387 × 1.4 ÷ 453.59 = 0.455 lb/ft (material $0.296/ft, not $0.50; total ≈ $0.407/ft, not $0.611). The 0.75 in² is also a perimeter × wall approximation where the exact hollow section is 0.6875 in². The tool follows the physics; documented in `docs/validation.md`.
3. **Physics identities:** film yield 27,680 ÷ (mils × SG) gives about 30,087 in²/lb for 1 mil LDPE (SG 0.92), consistent with the commonly quoted ~30,000; to be confirmed against a vendor square-inch table read at its primary page during the build. gsm = µm × g/cm³ checked by unit analysis.
4. **Algebraic checks:** a single-company chain collapses to the closed form; hand-offs only ever add cost (margin stacking is monotone in the number of hand-offs); cost is monotone in every input; price × (1 − margin) = cost at the last step; the waste line equals the difference of two direct runs; the low case ≤ base ≤ high case; kg/hr and m/min steps agree when the throughput is set to match the web speed.
5. **Hand-computed reference cases:** § 7, from a standalone script independent of the library, asserted to the cent.

## 7. Worked example (synthetic; every number is an illustration, not a market price)

Printed 3-layer sachet laminate. Materials (gsm · $/kg · enters at): PET 12 µm × 1.39 = 16.68 g/m² · $2.40 · print; ink 2.0 g/m² · $6.00 · print; adhesive 2.0 g/m² · $4.00 · laminate; PE sealant 60 µm × 0.92 = 55.2 g/m² · $2.10 · laminate. Web 1.00 m, 20 units per web metre (4 lanes ÷ 0.20 m repeat). Steps (rate · speed · setup hr · setup waste · run yield): print $140/hr · 150 m/min · 1.0 · 400 m · 98%; laminate $110 · 200 · 0.75 · 300 m · 99%; pouch-make $95 · 100 · 1.5 · 200 m · 99%. Order 1,000,000 good pouches; tooling $12,000 over 3,000,000 pouches (= $4,000 on this order); overhead 12%; margin 15% of price at each hand-off and at the end.

**A. One plant does all three steps:**

| Result | Value |
|---|---|
| Web input length by step (print / laminate / pouch-make) | 52,968.6 m / 51,517.2 m / 50,705.1 m |
| Material | $9,140.08 ($9.14 per 1,000) |
| Conversion: print / laminate / pouch-make | $963.96 / $554.74 / $945.33 = $2,464.03 |
| Cost of waste (vs. perfect yield, no setup waste) | $413.73 |
| Overhead (12% of material + conversion) | $1,392.49 |
| Tooling | $4,000.00 |
| **Cost** | **$16,996.60 ($17.00 per 1,000)** |
| **Price at 15% margin** | **$19,995.99 ($20.00 per 1,000)** |

**B. Vertical integration versus separate companies (same steps, same inputs):**

| Chain | Price per 1,000 | Margin in the price | vs. A |
|---|---|---|---|
| A. One company | $20.00 | $2,999 | — |
| B. Print + laminate in one company, pouch-make separate | $24.46 | $2,107 + $3,669 | +22% |
| C. All three separate | $26.51 | $735 + $2,340 + $3,976 | +33% |

**C. Rough range for A** (prices and rates ±15%, speeds ∓15%, run yields ±2 points, capped at 100%): **$17.09 / $20.00 / $23.67 per 1,000** (low / base / high). An outer bound, not a confidence interval.

**Decision illustration:** a $26.00 quote against A is $6.00 (30%) over the base and above the range, but it sits just under chain C ($26.51). The question to ask the supplier is not "why so high?" but "how many hand-offs are in this price?". Material is 54% of cost, so a 10% move in material prices shifts the price more than a 10% change in any one machine rate. Illustrations of output, not claims about any real supplier.

## 8. Non-goals / when NOT to use this

- **Rough estimation only.** The answer is a reference range for a negotiation, not proof that a quote is wrong, and the range is only as good as the rates and prices entered.
- **No market prices, indices or supplier data.** All prices and rates are yours.
- **One web width for the whole chain**, so a slit-down or an extrusion step at a different width is approximated. Not rigid packaging, thermoforming, injection molding or corrugate in v1.
- **Waste is step run yield plus fixed setup waste**, all valued at the cost carried into that step. No scrap resale or regrind credit.
- **Overhead and margin are percentages** (with per-step overrides). Plant allocation, freight, minimum order charges, payment terms and tariffs are outside v1.
- **No negotiation advice.** The tool shows where cost could sit; what to do about it is a business judgment.
- Not a substitute for a supplier cost-breakdown request or a costing audit.

## 9. Skill taught

Bottom-up cost modeling over a value chain: turning structure and process into a cost, seeing where it sits (material vs. yield vs. conversion vs. stacked margin), and how vertical integration changes the price.

## 10. Definition of Done

- [x] Spec approved (revised scope)
- [x] Core library (`opstoolkit/should_cost.py`) implemented, stdlib only
- [x] Tests pass: BN Pack example, DFMA structure + erratum, yield identity, algebraic and monotonicity checks (incl. hand-offs and the range), § 7 cases A, B, C
- [x] Vendor square-inch table read at its primary page and the LDPE figure confirmed
- [x] Browser page working, matches library output
- [x] Worked example + "when not to use" on the page
- [x] README table + hub page updated
- [x] `docs/validation.md` updated (including the DFMA erratum and the stated validation limit)
- [x] Deployed to Pages and checked live
- [x] KB pointer/state updated
