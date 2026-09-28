"""Make-vs-buy / TCO tests. Validation: (1) the published ABX Company example
(eCampusOntario, Fundamentals of Operations Management, section 4.10, verified at
the source 2026-09-28); (2) algebraic checks; (3) a hand-computed TCO case whose
expected values come from a standalone script independent of the library.
See docs/validation.md and docs/specs/02-make-vs-buy.md sections 6-7.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opstoolkit.make_vs_buy import (
    Option, capital_recovery_factor, compare, compare_from_dict,
)


def abx(volume=1000):
    make = Option("Make", fixed_annual=160_000, variable_per_unit=100)
    buy = Option("Buy", fixed_annual=0, variable_per_unit=150)
    return compare(make, buy, volume)


def tco_case(volume=3500):
    make = Option("Make", fixed_annual=160_000, one_time=90_000, variable_per_unit=100,
                  defect_rate=0.02, cost_per_defect=40, inventory_days=20, carrying_rate=0.20)
    buy = Option("Buy", fixed_annual=0, one_time=30_000, variable_per_unit=150,
                 defect_rate=0.01, cost_per_defect=40, inventory_days=45, carrying_rate=0.20,
                 risk_premium=0.05)
    return make, buy, volume


# --- Published example: ABX Company ----------------------------------------

def test_abx_break_even_is_3200():
    r = abx()
    assert r.break_even.kind == "crossover"
    assert r.break_even.volume == pytest.approx(3200)
    assert r.break_even.cheaper_above == "Make"
    assert r.break_even.cheaper_below == "Buy"


def test_abx_totals_at_1000_units():
    r = abx(1000)
    make, buy = r.options
    assert make.total_cost == pytest.approx(260_000)
    assert buy.total_cost == pytest.approx(150_000)
    assert r.preferred == "Buy"
    assert r.advantage == pytest.approx(110_000)


def test_abx_naive_equals_tco_when_adders_are_zero():
    r = abx()
    assert r.naive_break_even.volume == pytest.approx(r.break_even.volume)
    assert r.naive_preferred == r.preferred


def test_abx_make_preferred_above_break_even():
    assert abx(4000).preferred == "Make"
    assert abx(3000).preferred == "Buy"


# --- Algebraic checks -------------------------------------------------------

def test_equal_cost_at_break_even():
    make, buy, _ = tco_case()
    q_star = compare(make, buy, 1000).break_even.volume
    r = compare(make, buy, q_star)
    assert r.options[0].total_cost == pytest.approx(r.options[1].total_cost)
    assert r.preferred is None


def test_preferred_has_lower_total():
    make, buy, q = tco_case()
    r = compare(make, buy, q)
    lower = min(r.options, key=lambda o: o.total_cost)
    assert r.preferred == lower.name


def test_swapping_options_swaps_result():
    make, buy, q = tco_case()
    r1 = compare(make, buy, q)
    r2 = compare(buy, make, q)
    assert r1.preferred == r2.preferred
    assert r1.break_even.volume == pytest.approx(r2.break_even.volume)
    assert r1.break_even.cheaper_above == r2.break_even.cheaper_above


def test_volume_table_crosses_at_break_even():
    r = abx(3200)
    row = next(x for x in r.volume_table if x["factor"] == 1.0)
    assert row["cost_a"] == pytest.approx(row["cost_b"])
    below = next(x for x in r.volume_table if x["factor"] == 0.5)
    above = next(x for x in r.volume_table if x["factor"] == 2.0)
    assert below["cost_a"] > below["cost_b"]
    assert above["cost_a"] < above["cost_b"]


def test_capital_recovery_factor_closed_form():
    assert capital_recovery_factor(0.10, 5) == pytest.approx(0.2637974807)
    assert capital_recovery_factor(0.0, 4) == pytest.approx(0.25)


# --- Hand-computed TCO reference case (spec section 7) ----------------------

def test_tco_reference_case():
    make, buy, q = tco_case()
    r = compare(make, buy, q, horizon_years=5, discount_rate=0.10)
    a, b = r.options
    assert a.effective_fixed == pytest.approx(183741.77327152708)
    assert a.effective_variable == pytest.approx(101.8958904109589)
    assert b.effective_fixed == pytest.approx(7913.924423842357)
    assert b.effective_variable == pytest.approx(161.59863013698632)
    assert a.total_cost == pytest.approx(540377.3897098833)
    assert b.total_cost == pytest.approx(573509.1299032945)
    assert a.cost_per_unit == pytest.approx(540377.3897098833 / 3500)
    assert r.preferred == "Make"
    assert r.advantage == pytest.approx(33131.74019341124)
    assert r.advantage_pct == pytest.approx(33131.74019341124 / 573509.1299032945)
    assert r.break_even.volume == pytest.approx(2945.0549447906246)


def test_tco_reference_naive_comparison():
    make, buy, q = tco_case()
    r = compare(make, buy, q)
    assert r.naive_break_even.volume == pytest.approx(3200)
    na, nb = r.naive_options
    assert na.total_cost == pytest.approx(510_000)
    assert nb.total_cost == pytest.approx(525_000)
    assert r.naive_preferred == "Make"


def test_tco_reference_sensitivity_grid():
    make, buy, q = tco_case()
    g = compare(make, buy, q).sensitivity["break_even"]
    # rows: Buy variable -20%/base/+20%; columns: Make variable -20%/base/+20%
    assert g[1][1] == pytest.approx(2945.0549447906246)
    assert g[0][0] == pytest.approx(3687.4951062632103)
    assert g[0][2] == pytest.approx(24272.755230485913)
    assert g[2][0] == pytest.approx(1567.6290292729404)
    assert g[2][2] == pytest.approx(2451.475030727105)


def test_decision_statement():
    make, buy, q = tco_case()
    d = compare(make, buy, q).decision
    assert "Make is cheaper by $33,132 per year (5.8%)" in d
    assert "break-even volume is 2,945 units" in d
    assert "Make is cheaper above it and Buy below it" in d
    assert "3,200 units" in d


# --- Edge cases -------------------------------------------------------------

def test_dominated_when_one_option_is_cheaper_everywhere():
    a = Option("A", fixed_annual=1000, variable_per_unit=10)
    b = Option("B", fixed_annual=5000, variable_per_unit=12)
    r = compare(a, b, 500)
    assert r.break_even.kind == "dominated"
    assert r.break_even.cheaper_everywhere == "A"
    assert r.break_even.volume is None
    assert "A is cheaper at every volume" in r.decision


def test_dominated_when_break_even_would_be_negative():
    a = Option("A", fixed_annual=5000, variable_per_unit=12)
    b = Option("B", fixed_annual=1000, variable_per_unit=10)
    r = compare(a, b, 500)
    assert r.break_even.kind == "dominated"
    assert r.break_even.cheaper_everywhere == "B"


def test_parallel_when_variable_costs_equal():
    a = Option("A", fixed_annual=1000, variable_per_unit=10)
    b = Option("B", fixed_annual=4000, variable_per_unit=10)
    r = compare(a, b, 100)
    assert r.break_even.kind == "parallel"
    assert r.break_even.cheaper_everywhere == "A"


def test_identical_curves():
    a = Option("A", fixed_annual=1000, variable_per_unit=10)
    b = Option("B", fixed_annual=1000, variable_per_unit=10)
    r = compare(a, b, 100)
    assert r.break_even.kind == "identical"
    assert r.preferred is None
    assert "cost the same" in r.decision


def test_zero_volume():
    make, buy, _ = tco_case()
    r = compare(make, buy, 0)
    assert r.options[0].cost_per_unit is None
    assert r.options[0].total_cost == pytest.approx(r.options[0].effective_fixed)
    assert r.preferred == "Buy"  # lower fixed cost


def test_zero_discount_rate_annualizes_by_straight_line():
    a = Option("A", fixed_annual=0, one_time=1000, variable_per_unit=1)
    b = Option("B", fixed_annual=0, variable_per_unit=2)
    r = compare(a, b, 0, horizon_years=4, discount_rate=0.0)
    assert r.options[0].effective_fixed == pytest.approx(250)


def test_no_naive_crossover_phrase_when_only_tco_creates_one():
    # Naive: A has higher fixed and higher variable -> dominated. TCO: quality flips it.
    a = Option("A", fixed_annual=5000, variable_per_unit=11, defect_rate=0.0)
    b = Option("B", fixed_annual=1000, variable_per_unit=10, defect_rate=0.5, cost_per_defect=10)
    r = compare(a, b, 100)
    assert r.naive_break_even.kind == "dominated"
    assert r.break_even.kind == "crossover"
    assert "would have shown no break-even" in r.decision


# --- Input validation -------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    dict(name=" ", fixed_annual=0, variable_per_unit=1),
    dict(name="x", fixed_annual=-1, variable_per_unit=1),
    dict(name="x", fixed_annual=0, variable_per_unit=-1),
    dict(name="x", fixed_annual=0, variable_per_unit=1, one_time=-1),
    dict(name="x", fixed_annual=0, variable_per_unit=1, defect_rate=1.5),
    dict(name="x", fixed_annual=0, variable_per_unit=1, defect_rate=-0.1),
    dict(name="x", fixed_annual=0, variable_per_unit=1, cost_per_defect=-1),
    dict(name="x", fixed_annual=0, variable_per_unit=1, inventory_days=-1),
    dict(name="x", fixed_annual=0, variable_per_unit=1, carrying_rate=-0.1),
    dict(name="x", fixed_annual=0, variable_per_unit=1, risk_premium=-0.1),
])
def test_option_validation(kwargs):
    with pytest.raises(ValueError):
        Option(**kwargs)


def test_compare_validation():
    a = Option("A", fixed_annual=0, variable_per_unit=1)
    b = Option("B", fixed_annual=0, variable_per_unit=2)
    with pytest.raises(ValueError):
        compare(a, b, -1)
    with pytest.raises(ValueError):
        compare(a, b, 10, horizon_years=0)
    with pytest.raises(ValueError):
        compare(a, b, 10, horizon_years=11)
    with pytest.raises(ValueError):
        compare(a, b, 10, horizon_years=2.5)
    with pytest.raises(ValueError):
        compare(a, b, 10, discount_rate=-0.01)
    with pytest.raises(ValueError):
        compare(a, Option("A", fixed_annual=0, variable_per_unit=2), 10)


# --- JSON entry point (browser page) ---------------------------------------

def test_compare_from_dict_matches_and_serializes():
    make, buy, q = tco_case()
    payload = {
        "volume": q, "horizon_years": 5, "discount_rate": 0.10,
        "a": {"name": "Make", "fixed_annual": 160_000, "one_time": 90_000, "variable_per_unit": 100,
              "defect_rate": 0.02, "cost_per_defect": 40, "inventory_days": 20, "carrying_rate": 0.20,
              "risk_premium": 0.0},
        "b": {"name": "Buy", "fixed_annual": 0, "one_time": 30_000, "variable_per_unit": 150,
              "defect_rate": 0.01, "cost_per_defect": 40, "inventory_days": 45, "carrying_rate": 0.20,
              "risk_premium": 0.05},
    }
    out = compare_from_dict(payload)
    json.dumps(out)
    assert out["preferred"] == "Make"
    assert out["break_even"]["volume"] == pytest.approx(2945.0549447906246)
    assert out["options"][0]["total_cost"] == pytest.approx(540377.3897098833)
