"""Safety-stock / service-level optimizer tests. Validation: (1) published EOQ
examples and the kiosk safety-stock example from eCampusOntario, Fundamentals of
Operations Management, sections 8.5 and 8.7 (verified at the source 2026-09-28);
(2) independent numerical checks of the extension (loss function by numerical
integration, optimal service level by brute-force grid search); (3) a
hand-computed case from a standalone script. See docs/validation.md and
docs/specs/03-safety-stock.md sections 6-7.
"""

import json
import math
import sys
from pathlib import Path
from statistics import NormalDist

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opstoolkit.safety_stock import (
    Inputs, compute, compute_from_dict, eoq, normal_loss, order_cycle_cost,
)

N = NormalDist()


def annual(d, s, h, **kw):
    """Inputs where the period is one year, so annual demand = d."""
    return Inputs(mean_demand=d, demand_std=0, lead_time=1, periods_per_year=1,
                  order_cost=s, holding_cost=h, **kw)


def worked(**kw):
    args = dict(mean_demand=200, demand_std=40, lead_time=2, periods_per_year=52,
                order_cost=75, holding_cost=6, target_csl=0.95, shortage_cost=25)
    args.update(kw)
    return Inputs(**args)


# --- Published EOQ examples (section 8.5) -----------------------------------

def test_eoq_apple_canada():
    r = compute(annual(250_000, 150, 12))
    assert r.order_quantity == pytest.approx(2500)
    assert r.ordering_cost + r.cycle_holding_cost == pytest.approx(30_000)
    assert r.orders_per_year == pytest.approx(100)
    assert r.used_eoq


def test_eoq_bestbuy_laptops():
    r = compute(annual(1500, 625, 130))
    assert r.order_quantity == pytest.approx(120.1, abs=0.01)
    assert r.ordering_cost + r.cycle_holding_cost == pytest.approx(15_612.49, abs=0.02)
    assert r.orders_per_year == pytest.approx(12.49, abs=0.01)


def test_eoq_modern_furniture():
    r = compute(annual(45_000, 1500, 0.70))
    assert r.order_quantity == pytest.approx(13_887.3, abs=0.05)
    assert r.ordering_cost + r.cycle_holding_cost == pytest.approx(9_721.11, abs=0.02)
    assert r.orders_per_year == pytest.approx(3.24, abs=0.005)


def test_eoq_function_and_cost_at_optimum_are_balanced():
    q = eoq(10_400, 75, 6)
    assert 75 * 10_400 / q == pytest.approx(6 * q / 2)  # ordering = holding at the optimum
    assert order_cycle_cost(10_400, 75, 6, q) <= order_cycle_cost(10_400, 75, 6, q * 1.1)
    assert order_cycle_cost(10_400, 75, 6, q) <= order_cycle_cost(10_400, 75, 6, q * 0.9)


# --- Published safety-stock example (section 8.7, cell-phone kiosk) ---------

def test_kiosk_safety_stock():
    r = compute(Inputs(mean_demand=20, demand_std=4, lead_time=1, order_cost=10, holding_cost=1,
                       target_csl=0.90))
    assert r.lead_time_demand_std == pytest.approx(4)
    # The book uses a table-rounded z of 1.28 -> 5.12; the tool uses the exact z = 1.2816.
    assert r.target.safety_stock == pytest.approx(5.12, abs=0.01)
    assert round(r.target.safety_stock) == 5  # the book's "or 5"


def test_kiosk_reorder_point_uses_mean_not_std():
    # The book prints ROP = 4 + 5 = 9 (std dev instead of mean lead-time demand).
    # The page's own formula, ROP = mean lead-time demand + SS, gives ~25. Documented erratum.
    r = compute(Inputs(mean_demand=20, demand_std=4, lead_time=1, order_cost=10, holding_cost=1,
                       target_csl=0.90))
    assert r.lead_time_demand_mean == pytest.approx(20)
    assert r.reorder_point == pytest.approx(20 + 5.126, abs=0.01)
    assert r.reorder_point != pytest.approx(9, abs=1)


def test_lead_time_scaling_sqrt():
    a = compute(worked(lead_time=1))
    b = compute(worked(lead_time=4))
    assert b.lead_time_demand_std == pytest.approx(2 * a.lead_time_demand_std)
    assert b.lead_time_demand_mean == pytest.approx(4 * a.lead_time_demand_mean)


# --- Independent checks of the extension ------------------------------------

def test_normal_loss_known_table_values():
    assert normal_loss(0) == pytest.approx(0.3989, abs=1e-4)
    assert normal_loss(1) == pytest.approx(0.0833, abs=1e-4)
    assert normal_loss(2) == pytest.approx(0.0085, abs=1e-4)


@pytest.mark.parametrize("z", [-1.0, 0.0, 0.5, 1.28, 2.33, 3.0])
def test_normal_loss_matches_numerical_integration(z):
    # G(z) = integral from z to infinity of (x - z) * phi(x) dx, by Simpson's rule.
    n, hi = 200_000, z + 12
    step = (hi - z) / n
    f = lambda x: (x - z) * N.pdf(x)
    total = f(z) + f(hi)
    for k in range(1, n):
        total += f(z + k * step) * (4 if k % 2 else 2)
    assert normal_loss(z) == pytest.approx(total * step / 3, abs=1e-8)


def test_optimal_z_matches_brute_force_grid_search():
    i = worked()
    r = compute(i)
    sigma, q, d = r.lead_time_demand_std, r.order_quantity, r.annual_demand
    cost = lambda z: i.holding_cost * sigma * z + (d / q) * i.shortage_cost * sigma * normal_loss(z)
    best_z = min((k * 1e-4 for k in range(0, 50_001)), key=cost)
    assert r.optimum.z == pytest.approx(best_z, abs=2e-4)
    assert r.optimum.safety_plus_stockout == pytest.approx(cost(best_z), abs=1e-3)
    # Nothing on the grid beats it, and it beats every table row and the target.
    assert all(cost(k * 0.01) >= r.optimum.safety_plus_stockout - 1e-9 for k in range(0, 500))
    assert all(r.optimum.safety_plus_stockout <= row.total_cost + 1e-9 for row in r.table)
    assert r.optimum.saving_vs_target >= 0


def test_fill_rate_and_csl_identities():
    r = compute(worked())
    for row in r.table:
        assert N.cdf(row.z) == pytest.approx(row.csl)
        assert row.fill_rate == pytest.approx(1 - row.expected_short_per_cycle / r.order_quantity)
        assert row.safety_stock == pytest.approx(row.z * r.lead_time_demand_std)
    # Fill rate is much higher than CSL at mid service levels; carrying cost rises, stockouts fall.
    assert r.table[3].fill_rate > r.table[3].csl
    carry = [row.carrying_cost for row in r.table]
    stock = [row.stockout_cost for row in r.table]
    assert carry == sorted(carry)
    assert stock == sorted(stock, reverse=True)


def test_step_costs_sum_to_carrying_difference():
    r = compute(worked())
    assert r.table[0].step_cost is None
    steps = sum(row.step_cost for row in r.table[1:])
    assert steps == pytest.approx(r.table[-1].carrying_cost - r.table[0].carrying_cost)


# --- Hand-computed reference case (spec section 7) --------------------------

def test_reference_case_core_numbers():
    r = compute(worked())
    assert r.annual_demand == 10_400
    assert r.lead_time_demand_mean == pytest.approx(400)
    assert r.lead_time_demand_std == pytest.approx(56.568542494923804)
    assert r.order_quantity == pytest.approx(509.9019513592785)
    assert r.orders_per_year == pytest.approx(20.396078054371138)
    assert r.ordering_cost == pytest.approx(1529.7058540778355)
    assert r.cycle_holding_cost == pytest.approx(1529.7058540778355)


def test_reference_case_target_95():
    t = compute(worked()).target
    assert t.z == pytest.approx(1.6449, abs=5e-5)
    assert t.safety_stock == pytest.approx(93.05, abs=0.01)
    assert t.carrying_cost == pytest.approx(558.28, abs=0.01)
    assert t.stockout_cost == pytest.approx(602.65, abs=0.01)
    assert t.total_cost == pytest.approx(1160.93, abs=0.01)
    assert t.fill_rate == pytest.approx(0.99768, abs=1e-5)
    r = compute(worked())
    assert r.reorder_point == pytest.approx(493.05, abs=0.01)
    assert r.total_inventory_cost == pytest.approx(4220.34, abs=0.02)


def test_reference_case_optimum():
    o = compute(worked()).optimum
    assert o.critical_ratio == pytest.approx(0.988233031891709)
    assert o.csl == pytest.approx(0.988233031891709)
    assert o.z == pytest.approx(2.2646537420937363)
    assert o.safety_stock == pytest.approx(128.10816144591774)
    assert o.carrying_cost == pytest.approx(768.6489686755065)
    assert o.stockout_cost == pytest.approx(117.07440311507422)
    assert o.safety_plus_stockout == pytest.approx(885.7233717905807)
    assert o.saving_vs_target == pytest.approx(275.2035, abs=0.001)
    assert not o.clamped_at_zero


@pytest.mark.parametrize("idx,z,ss,carry,stock,total", [
    (0, 0.8416, 47.61, 285.66, 3220.12, 3505.78),
    (2, 1.2816, 72.50, 434.97, 1365.59, 1800.56),
    (3, 1.6449, 93.05, 558.28, 602.65, 1160.93),
    (5, 2.3263, 131.60, 789.59, 97.74, 887.33),
    (7, 3.0902, 174.81, 1048.86, 7.99, 1056.85),
])
def test_reference_case_service_table(idx, z, ss, carry, stock, total):
    row = compute(worked()).table[idx]
    assert row.z == pytest.approx(z, abs=5e-5)
    assert row.safety_stock == pytest.approx(ss, abs=0.01)
    assert row.carrying_cost == pytest.approx(carry, abs=0.01)
    assert row.stockout_cost == pytest.approx(stock, abs=0.01)
    assert row.total_cost == pytest.approx(total, abs=0.01)


def test_decision_statements():
    d = compute(worked()).decision
    assert "95.0% cycle service level" in d
    assert "93.0 units of safety stock" in d  # 93.047 exact
    assert "reorder point 493.0 units" in d  # 493.047 exact
    assert "98.82%" in d
    assert "$1,161 to $886" in d
    assert "saving of $275 per year" in d
    no_p = compute(worked(shortage_cost=None)).decision
    assert "Add a cost per unit short" in no_p


# --- Edge cases -------------------------------------------------------------

def test_without_shortage_cost_no_optimum_or_stockout_columns():
    r = compute(worked(shortage_cost=None))
    assert r.optimum is None
    assert r.target.stockout_cost is None
    assert all(row.total_cost is None for row in r.table)
    assert r.total_inventory_cost == pytest.approx(r.ordering_cost + r.cycle_holding_cost + r.target.carrying_cost)


def test_zero_demand_variability_needs_no_safety_stock():
    r = compute(worked(demand_std=0))
    assert r.target.safety_stock == 0
    assert r.target.fill_rate == 1
    assert r.reorder_point == pytest.approx(r.lead_time_demand_mean)


def test_optimum_clamps_at_zero_when_shortage_is_cheap():
    r = compute(worked(shortage_cost=0.01))  # ratio = Q*H/(p*D) >> 1
    assert r.optimum.clamped_at_zero
    assert r.optimum.csl == 0.5
    assert r.optimum.safety_stock == 0
    assert "does not pay for itself" in r.decision


def test_zero_shortage_cost_clamps_too():
    r = compute(worked(shortage_cost=0))
    assert r.optimum.clamped_at_zero


def test_user_entered_order_quantity_overrides_eoq():
    r = compute(worked(order_quantity=800))
    assert r.order_quantity == 800
    assert not r.used_eoq
    assert r.ordering_cost == pytest.approx(75 * 10_400 / 800)
    assert r.cycle_holding_cost == pytest.approx(6 * 800 / 2)


def test_entered_q_with_zero_order_cost_is_allowed():
    r = compute(worked(order_cost=0, order_quantity=500))
    assert r.ordering_cost == 0


def test_higher_shortage_cost_pushes_service_level_up():
    lo = compute(worked(shortage_cost=10)).optimum.csl
    hi = compute(worked(shortage_cost=100)).optimum.csl
    assert hi > lo


# --- Input validation -------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    dict(mean_demand=0),
    dict(mean_demand=-1),
    dict(demand_std=-1),
    dict(lead_time=0),
    dict(periods_per_year=0),
    dict(order_cost=-1),
    dict(order_cost=0),  # blank Q + zero order cost: EOQ undefined
    dict(holding_cost=0),
    dict(holding_cost=-1),
    dict(order_quantity=0),
    dict(order_quantity=-5),
    dict(target_csl=0.4),
    dict(target_csl=1.0),
    dict(shortage_cost=-1),
])
def test_input_validation(kwargs):
    with pytest.raises(ValueError):
        worked(**kwargs)


# --- JSON entry point (browser page) ----------------------------------------

def test_compute_from_dict_matches_and_serializes():
    payload = dict(mean_demand=200, demand_std=40, lead_time=2, periods_per_year=52,
                   order_cost=75, holding_cost=6, order_quantity=None, target_csl=0.95, shortage_cost=25)
    out = compute_from_dict(payload)
    json.dumps(out)
    assert out["optimum"]["csl"] == pytest.approx(0.988233031891709)
    assert out["target"]["safety_stock"] == pytest.approx(93.05, abs=0.01)
    assert len(out["table"]) == 8
