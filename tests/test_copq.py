"""COPQ calculator tests. Validation is definitional (ASQ PAF identities) plus a
hand-computed reference case whose expected values were produced by a
standalone script, independent of opstoolkit/copq.py. See docs/validation.md
and docs/specs/01-copq.md sections 6-7.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opstoolkit.copq import (
    APPRAISAL, EXTERNAL_FAILURE, INTERNAL_FAILURE, PREVENTION,
    LineItem, Project, compute_copq, compute_from_dict,
)


def example_items():
    return [
        LineItem("Training", PREVENTION, annual_cost=60_000),
        LineItem("Process FMEA / QMS upkeep", PREVENTION, annual_cost=90_000),
        LineItem("Incoming inspection", APPRAISAL, annual_cost=120_000),
        LineItem("Final inspection", APPRAISAL, annual_cost=180_000),
        LineItem("Calibration", APPRAISAL, annual_cost=40_000),
        LineItem("Scrap", INTERNAL_FAILURE, units=12_000, unit_cost=85, reduction=0.40),
        LineItem("Rework", INTERNAL_FAILURE, units=8_000, unit_cost=30, reduction=0.50),
        LineItem("Customer returns", EXTERNAL_FAILURE, units=900, unit_cost=210, reduction=0.30),
        LineItem("Warranty", EXTERNAL_FAILURE, annual_cost=110_000, reduction=0.30),
    ]


EXAMPLE_PROJECT = Project(one_time_cost=250_000, added_annual_spend=60_000, horizon_years=3, discount_rate=0.10)


# --- Definitional identities (ASQ PAF framework) ---------------------------

def test_coq_equals_cogq_plus_copq():
    r = compute_copq(example_items(), revenue=50_000_000)
    assert r.coq == pytest.approx(r.cogq + r.copq)


def test_category_shares_sum_to_one():
    r = compute_copq(example_items())
    assert sum(r.category_shares.values()) == pytest.approx(1.0)


def test_driver_mode_equals_direct_mode():
    driver = LineItem("x", INTERNAL_FAILURE, units=12_000, unit_cost=85)
    direct = LineItem("x", INTERNAL_FAILURE, annual_cost=1_020_000)
    assert driver.cost == direct.cost


# --- Hand-computed reference case (spec section 7) -------------------------

def test_baseline_reference_case():
    r = compute_copq(example_items(), revenue=50_000_000)
    assert r.category_totals[PREVENTION] == 150_000
    assert r.category_totals[APPRAISAL] == 340_000
    assert r.category_totals[INTERNAL_FAILURE] == 1_260_000
    assert r.category_totals[EXTERNAL_FAILURE] == 299_000
    assert r.coq == 2_049_000
    assert r.copq == 1_559_000
    assert r.coq_pct_revenue == pytest.approx(0.04098)
    assert r.copq / r.coq == pytest.approx(0.7608589555880918)


def test_project_reference_case():
    p = compute_copq(example_items(), revenue=50_000_000, project=EXAMPLE_PROJECT).project
    assert p.savings_by_line["Scrap"] == pytest.approx(408_000)
    assert p.savings_by_line["Rework"] == pytest.approx(120_000)
    assert p.savings_by_line["Customer returns"] == pytest.approx(56_700)
    assert p.savings_by_line["Warranty"] == pytest.approx(33_000)
    assert p.gross_savings == pytest.approx(617_700)
    assert p.net_annual_savings == pytest.approx(557_700)
    assert p.post_project_coq == pytest.approx(1_491_300)
    assert p.post_project_coq_pct_revenue == pytest.approx(0.029826)
    assert p.payback_months == pytest.approx(5.3792361484669176)
    assert p.npv == pytest.approx(1_136_917.3553719006)


def test_npv_matches_closed_form_annuity():
    r, years, net, one_time = 0.10, 3, 557_700, 250_000
    closed = net * (1 - (1 + r) ** -years) / r - one_time
    p = compute_copq(example_items(), project=EXAMPLE_PROJECT).project
    assert p.npv == pytest.approx(closed)


def test_sensitivity_grid():
    p = compute_copq(example_items(), project=EXAMPLE_PROJECT).project
    grid = p.sensitivity["npv"]
    # Center cell (100% achieved, base cost) is the base-case NPV.
    assert grid[2][1] == pytest.approx(p.npv)
    # Half the reduction at base cost, closed form.
    annuity = (1 - 1.10 ** -3) / 0.10
    assert grid[0][1] == pytest.approx((617_700 * 0.5 - 60_000) * annuity - 250_000)
    # Costlier project is never better than a cheaper one at the same achievement.
    for row in grid:
        assert row[0] > row[1] > row[2]


def test_decision_statement():
    d = compute_copq(example_items(), project=EXAMPLE_PROJECT).project.decision
    assert "$557,700 per year net" in d
    assert "5.4 months" in d
    assert "$1,136,917" in d
    assert "10% discount rate" in d


# --- Edge cases -------------------------------------------------------------

def test_revenue_blank_or_zero_gives_na_percentages():
    for revenue in (None, 0):
        r = compute_copq(example_items(), revenue=revenue, project=EXAMPLE_PROJECT)
        assert r.coq_pct_revenue is None
        assert r.copq_pct_revenue is None
        assert r.project.post_project_coq_pct_revenue is None


def test_no_project_gives_no_project_result():
    assert compute_copq(example_items()).project is None


def test_payback_never_when_net_savings_not_positive():
    items = [LineItem("Scrap", INTERNAL_FAILURE, annual_cost=100_000, reduction=0.10)]
    p = compute_copq(items, project=Project(one_time_cost=50_000, added_annual_spend=10_000)).project
    assert p.net_annual_savings == 0
    assert p.payback_months is None
    assert "never pays back" in p.decision


def test_zero_discount_rate_is_simple_sum():
    items = [LineItem("Scrap", INTERNAL_FAILURE, annual_cost=100_000, reduction=0.5)]
    p = compute_copq(items, project=Project(one_time_cost=40_000, discount_rate=0.0, horizon_years=4)).project
    assert p.npv == pytest.approx(50_000 * 4 - 40_000)


def test_zero_one_time_cost_pays_back_immediately():
    items = [LineItem("Scrap", INTERNAL_FAILURE, annual_cost=100_000, reduction=0.5)]
    p = compute_copq(items, project=Project(one_time_cost=0)).project
    assert p.payback_months == 0


def test_all_zero_costs_do_not_divide_by_zero():
    r = compute_copq([LineItem("x", PREVENTION, annual_cost=0)], revenue=1_000_000)
    assert r.coq == 0
    assert all(s == 0 for s in r.category_shares.values())


# --- Input validation -------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    dict(category="bogus", annual_cost=1),
    dict(category=PREVENTION),                                  # neither mode
    dict(category=PREVENTION, annual_cost=1, units=1, unit_cost=1),   # both modes
    dict(category=PREVENTION, units=5),                         # half a driver
    dict(category=PREVENTION, annual_cost=-1),
    dict(category=PREVENTION, units=-1, unit_cost=1),
    dict(category=PREVENTION, annual_cost=1, reduction=1.5),
    dict(category=PREVENTION, annual_cost=1, reduction=-0.1),
])
def test_line_item_validation(kwargs):
    with pytest.raises(ValueError):
        LineItem("x", **kwargs)


@pytest.mark.parametrize("kwargs", [
    dict(one_time_cost=-1),
    dict(one_time_cost=0, added_annual_spend=-1),
    dict(one_time_cost=0, horizon_years=0),
    dict(one_time_cost=0, horizon_years=11),
    dict(one_time_cost=0, horizon_years=2.5),
    dict(one_time_cost=0, discount_rate=-0.01),
])
def test_project_validation(kwargs):
    with pytest.raises(ValueError):
        Project(**kwargs)


def test_compute_validation():
    with pytest.raises(ValueError):
        compute_copq([])
    with pytest.raises(ValueError):
        compute_copq(example_items(), revenue=-1)
    dup = [LineItem("a", PREVENTION, annual_cost=1), LineItem("a", APPRAISAL, annual_cost=1)]
    with pytest.raises(ValueError):
        compute_copq(dup)


# --- JSON entry point (browser page) ---------------------------------------

def test_compute_from_dict_matches_dataclass_path_and_serializes():
    payload = {
        "revenue": 50_000_000,
        "items": [
            {"name": "Scrap", "category": INTERNAL_FAILURE, "units": 12_000, "unit_cost": 85, "reduction": 0.4},
            {"name": "Training", "category": PREVENTION, "annual_cost": 60_000},
        ],
        "project": {"one_time_cost": 10_000, "added_annual_spend": 0, "horizon_years": 2, "discount_rate": 0.05},
    }
    out = compute_from_dict(payload)
    json.dumps(out)  # must be JSON-serializable for Pyodide -> JS
    assert out["coq"] == 1_080_000
    assert out["project"]["gross_savings"] == pytest.approx(408_000)


def test_compute_from_dict_without_project():
    out = compute_from_dict({"revenue": None, "items": [{"name": "a", "category": PREVENTION, "annual_cost": 5}]})
    assert out["project"] is None
