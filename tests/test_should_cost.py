"""Process-chain should-cost tests. Validation is STRUCTURAL and ARITHMETIC (spec
section 6): no authoritative published end-to-end should-cost exists. (1) The BN
Pack film-yield worked example (50,000 -> 47,000 pouches, $0.09, $0.097) and its
3-lane variant, read at the primary page 2026-10-01; (2) the DFMA extrusion
example's structure (die amortization, rate / speed), with its printed weight step
documented as an ERROR (0.77 lb/ft; correct 0.455) and NOT reproduced; (3) the
film-yield identity from 1 lb water = 27.68 in3; (4) algebraic and monotonicity
properties; (5) hand-computed reference cases A, B, C and the range from a
standalone script (spec section 7). See docs/validation.md.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opstoolkit.should_cost import (
    Inputs, Material, Step, compute, compute_from_dict, film_yield_in2_per_lb,
)


# --- Section 7 reference chain ----------------------------------------------
def chain(handoffs=(), **kw):
    mats = [Material("PET", 2.40, "print", thickness_um=12, density=1.39), Material("ink", 6.0, "print", gsm=2.0),
            Material("adhesive", 4.0, "laminate", gsm=2.0), Material("PE", 2.10, "laminate", thickness_um=60, density=0.92)]
    steps = [Step("print", 140, 150, setup_hr=1.0, setup_waste_m=400, run_yield=0.98, handoff="print" in handoffs),
             Step("laminate", 110, 200, setup_hr=0.75, setup_waste_m=300, run_yield=0.99, handoff="laminate" in handoffs),
             Step("pouch-make", 95, 100, setup_hr=1.5, setup_waste_m=200, run_yield=0.99)]
    args = dict(units=1_000_000, units_per_m=20, web_width_m=1.0, tooling_cost=12000, tooling_amort_qty=3_000_000)
    args.update(kw)
    return Inputs(mats, steps, **args)


def test_case_a_one_company():
    r = compute(chain())
    assert [round(s.input_length_m, 1) for s in r.stages] == [52968.6, 51517.2, 50705.1]
    assert r.material_total == pytest.approx(9140.08, abs=0.01)
    assert [round(s.conversion_cost, 2) for s in r.stages] == [963.96, 554.74, 945.33]
    assert r.conversion_total == pytest.approx(2464.03, abs=0.01)
    assert r.waste_cost == pytest.approx(413.73, abs=0.01)
    assert r.overhead_total == pytest.approx(1392.49, abs=0.01)
    assert r.tooling_total == pytest.approx(4000.00, abs=0.01)
    assert r.cost == pytest.approx(16996.60, abs=0.01)
    assert r.price == pytest.approx(19995.99, abs=0.01)
    assert r.price_per_1000 == pytest.approx(19.996, abs=0.001)


def test_case_b_and_c_margin_stacking():
    b = compute(chain(("laminate",)))
    c = compute(chain(("print", "laminate")))
    assert b.price == pytest.approx(24457.19, abs=0.01)
    assert [round(s.margin, 2) for s in b.stages if s.is_handoff] == [2106.68, 3668.58]
    assert c.price == pytest.approx(26508.77, abs=0.01)
    assert [round(s.margin, 2) for s in c.stages] == [735.25, 2340.23, 3976.32]
    a = compute(chain())
    assert a.price < b.price < c.price


def test_range_low_base_high():
    r = compute(chain())
    assert r.low_per_1000 == pytest.approx(17.09, abs=0.01)
    assert r.high_per_1000 == pytest.approx(23.67, abs=0.01)
    assert r.low_per_1000 < r.price_per_1000 < r.high_per_1000


# --- BN Pack worked example (vendor page; weak authority, labeled) -----------
def single(**kw):
    # gsm x price chosen so a 2,500 m roll of 0.96 m web costs $4,230: 2500 x 0.96 x 1000 x 1.7625 / 1000
    mats = [Material("film", 1.7625, "run", gsm=1000.0)]
    steps = [Step("run", 0.0, 100.0, run_yield=0.94)]
    args = dict(units=47000, units_per_m=20, web_width_m=0.96, overhead=0.0, margin=0.0)
    args.update(kw)
    return Inputs(mats, steps, **args)


def test_bn_pack_example():
    r = compute(single())
    assert r.stages[0].input_length_m == pytest.approx(2500.0)  # one roll -> 47,000 good at 94%
    assert r.material_total == pytest.approx(4230.0)
    assert r.price / 47000 == pytest.approx(0.09)
    # tooling 0.004 + testing 0.001 + quality loss 0.002 = 0.007 per unit -> 0.097
    r2 = compute(single(tooling_cost=0.007 * 47000, tooling_amort_qty=47000))
    assert r2.price / 47000 == pytest.approx(0.097)


def test_bn_pack_theoretical_output_and_three_lane_variant():
    # theoretical output of a 2,500 m roll with perfect yield: (2500 / 0.20) * lanes
    for lanes, expect in [(4, 50000), (3, 37500)]:
        r = compute(Inputs([Material("film", 1.0, "run", gsm=1000.0)], [Step("run", 0.0, 100.0)],
                           units=expect, units_per_m=lanes / 0.20, web_width_m=0.96, overhead=0.0, margin=0.0))
        assert r.stages[0].input_length_m == pytest.approx(2500.0)


def test_combined_yield_compounds_multiplicatively():
    steps = [Step("a", 0, 1, run_yield=0.98), Step("b", 0, 1, run_yield=0.99), Step("c", 0, 1, run_yield=0.96)]
    r = compute(Inputs([Material("m", 1.0, "a", gsm=1.0)], steps, units=10000, units_per_m=1, overhead=0, margin=0))
    assert r.stages[0].input_length_m == pytest.approx(10000 / (0.98 * 0.99 * 0.96))
    assert 0.98 * 0.99 * 0.96 == pytest.approx(0.9314, abs=5e-5)  # not 0.93 by adding losses


# --- DFMA extrusion structure; source error documented ----------------------
def test_dfma_die_and_processing_structure():
    # $80/hr / (50 ft/min * 60) = $0.0267 per ft; die $8,000 / 2,000,000 ft = $0.004 per ft.
    steps = [Step("extrude", 80.0, 50.0)]
    r = compute(Inputs([], steps, units=1.0, units_per_m=1.0, tooling_cost=8000, tooling_amort_qty=2_000_000,
                       overhead=0, margin=0))
    assert r.conversion_total == pytest.approx(80 / (50 * 60))
    assert r.tooling_total == pytest.approx(0.004)


def test_dfma_printed_weight_step_is_a_unit_error():
    printed = 0.75 * 12 * 1.4 / 16.387  # the page's expression, labeled "lb/ft"
    correct_lb_per_ft = 0.75 * 12 * 16.387 * 1.4 / 453.592
    assert printed == pytest.approx(0.769, abs=0.001)
    assert correct_lb_per_ft == pytest.approx(0.455, abs=0.001)
    assert abs(correct_lb_per_ft - printed) > 0.3  # tool follows physics, not the printed 0.77
    assert correct_lb_per_ft * 0.65 == pytest.approx(0.296, abs=0.001)


# --- Physics identities ------------------------------------------------------
def test_film_yield_identity():
    assert film_yield_in2_per_lb(1.0, 0.92) == pytest.approx(30087, abs=1)
    assert film_yield_in2_per_lb(2.0, 0.92) == pytest.approx(film_yield_in2_per_lb(1.0, 0.92) / 2)
    # 1 lb water = 27.68 in3: 1 in3 = 16.387 cm3 = 16.387 g = 0.036127 lb
    assert 1 / (16.387 / 453.592) == pytest.approx(27.68, abs=0.01)


def test_material_gsm_from_thickness_and_density():
    assert Material("m", 1.0, "s", thickness_um=60, density=0.92).weight_gsm == pytest.approx(55.2)
    assert Material("m", 1.0, "s", gsm=2.0).weight_gsm == 2.0


# --- Algebra and monotonicity ------------------------------------------------
def test_single_company_collapses_to_closed_form():
    r = compute(chain())
    base = r.material_total + r.conversion_total
    assert r.price == pytest.approx((base * 1.12 + 4000.0) / 0.85)


def test_price_times_one_minus_margin_equals_cost_at_last_step():
    r = compute(chain())
    last = r.stages[-1]
    assert last.price_out * (1 - 0.15) == pytest.approx(last.base * 1.12 + last.tooling)


def test_waste_line_is_difference_of_two_runs():
    clean = chain()
    r = compute(clean)
    perfect_steps = [Step(s.name, s.rate_per_hr, s.speed, setup_hr=s.setup_hr, setup_waste_m=0, run_yield=1.0)
                     for s in clean.steps]
    r0 = compute(Inputs(clean.materials, perfect_steps, units=clean.units, units_per_m=clean.units_per_m,
                        tooling_cost=12000, tooling_amort_qty=3_000_000))
    assert r.waste_cost == pytest.approx((r.material_total + r.conversion_total) - (r0.material_total + r0.conversion_total))
    assert r0.waste_cost == pytest.approx(0.0, abs=1e-9)


def test_cost_is_monotone_in_inputs():
    base = compute(chain()).price
    worse_yield = [Step(s.name, s.rate_per_hr, s.speed, setup_hr=s.setup_hr, setup_waste_m=s.setup_waste_m,
                        run_yield=s.run_yield - 0.02) for s in chain().steps]
    assert compute(Inputs(chain().materials, worse_yield, units=1_000_000, units_per_m=20, tooling_cost=12000,
                          tooling_amort_qty=3_000_000)).price > base
    assert compute(chain(overhead=0.20)).price > base
    assert compute(chain(margin=0.25)).price > base
    assert compute(chain(units=500_000)).price / 500_000 > base / 1_000_000  # setup spread over fewer units


def test_kg_per_hr_step_matches_equivalent_m_per_min_step():
    mats = [Material("film", 2.0, "ext", gsm=50.0)]
    web, width = 100.0, 1.0  # 100 m/min x 1 m x 50 g/m2 = 5 kg/min = 300 kg/hr
    a = compute(Inputs(mats, [Step("ext", 90, 100.0, "m_per_min")], units=60000, units_per_m=1, web_width_m=width,
                       overhead=0, margin=0))
    b = compute(Inputs(mats, [Step("ext", 90, 300.0, "kg_per_hr")], units=60000, units_per_m=1, web_width_m=width,
                       overhead=0, margin=0))
    assert a.conversion_total == pytest.approx(b.conversion_total)


def test_kg_per_hr_uses_cumulative_gsm_of_materials_entered_so_far():
    mats = [Material("a", 1.0, "s1", gsm=10.0), Material("b", 1.0, "s2", gsm=30.0)]
    steps = [Step("s1", 100, 100.0), Step("s2", 100, 40.0, "kg_per_hr")]
    r = compute(Inputs(mats, steps, units=1000, units_per_m=1, overhead=0, margin=0))
    # second step processes 1000 m x 1 m x (10 + 30) g/m2 = 40 kg at 40 kg/hr = 1 hour -> $100
    assert r.stages[1].conversion_cost == pytest.approx(100.0)


def test_handoff_only_adds_cost():
    p0 = compute(chain()).price
    p1 = compute(chain(("laminate",))).price
    p2 = compute(chain(("print", "laminate"))).price
    assert p0 < p1 < p2


def test_per_step_overrides_apply_at_handoffs():
    c = chain(("laminate",))
    steps = list(c.steps)
    steps[1] = Step(steps[1].name, steps[1].rate_per_hr, steps[1].speed, setup_hr=0.75, setup_waste_m=300,
                    run_yield=0.99, handoff=True, overhead=0.0, margin=0.0)
    flat = compute(Inputs(c.materials, steps, units=c.units, units_per_m=c.units_per_m, tooling_cost=12000,
                          tooling_amort_qty=3_000_000))
    assert flat.stages[1].margin == 0.0 and flat.stages[1].overhead == 0.0
    assert flat.price == pytest.approx(compute(chain()).price)  # a zero-markup hand-off changes nothing


def test_sensitivity_directions():
    r = compute(chain())
    d = {s.label: s.change_per_1000 for s in r.sensitivity}
    assert all(v > 0 for v in d.values())
    assert d["Material prices +10%"] > d["Machine rates +10%"]  # material is ~54% of cost


# --- Quote comparison --------------------------------------------------------
def test_quote_position_and_implied_margin():
    r = compute(chain(quote_per_1000=26.0))
    assert r.quote_position == "above"
    assert r.quote_gap == pytest.approx(26.0 - 19.99599, abs=0.001)
    assert r.implied_margin == pytest.approx(1 - 16.99660 / 26.0, abs=1e-4)
    assert compute(chain(quote_per_1000=20.0)).quote_position == "inside"
    assert compute(chain(quote_per_1000=15.0)).quote_position == "below"
    assert compute(chain()).quote_position is None


# --- Validation, entry point -------------------------------------------------
def test_bad_inputs_rejected():
    with pytest.raises(ValueError):
        Step("s", 10, 0)  # speed
    with pytest.raises(ValueError):
        Step("s", 10, 1, run_yield=0)
    with pytest.raises(ValueError):
        Step("s", 10, 1, speed_unit="furlongs")
    with pytest.raises(ValueError):
        Material("m", 1.0, "s")  # no gsm or thickness/density
    with pytest.raises(ValueError):
        Inputs([Material("m", 1.0, "ghost", gsm=1.0)], [Step("s", 1, 1)], units=1, units_per_m=1)
    with pytest.raises(ValueError):
        Inputs([], [Step("s", 1, 1), Step("s", 1, 1)], units=1, units_per_m=1)
    with pytest.raises(ValueError):
        Inputs([], [], units=1, units_per_m=1)
    with pytest.raises(ValueError):
        chain(margin=1.0)


def test_compute_from_dict_is_json_serializable():
    payload = dict(
        materials=[dict(name="film", price_per_kg=2.0, step="run", gsm=50.0)],
        steps=[dict(name="run", rate_per_hr=100.0, speed=100.0, run_yield=0.97)],
        units=100000, units_per_m=10, web_width_m=1.0, overhead=0.1, margin=0.2, quote_per_1000=30.0,
    )
    out = compute_from_dict(payload)
    json.dumps(out)
    assert out["price"] > 0 and out["quote_position"] in ("below", "inside", "above")
