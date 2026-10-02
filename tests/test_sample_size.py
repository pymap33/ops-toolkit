"""Sample-size / cost-of-testing planner tests. Validation: (1) the Minitab
"Power and Sample Size for 2-Sample t" example (n = 86 per group, actual power
0.903230) and the NIST/SEMATECH e-Handbook section 7.2.2.2 one-sample example
(n = 11 by the t-iteration), both reproduced independently 2026-10-01;
(2) the stdlib noncentral-t machinery against SciPy reference values (SciPy was
used once to generate the constants below, never by the library); (3) property
checks (monotonicity, normal limit, brute-force cost scan); (4) the section 7
worked example. See docs/validation.md and docs/specs/04-sample-size.md
sections 6-7. The NIST sample-size TABLE is deliberately not asserted: its
method is unverified (spec section 6, item 3).
"""

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opstoolkit.sample_size import (
    Inputs, compute, compute_from_dict, normal_approx_n, required_n, t_power, t_quantile, t_sf,
)

# --- Machinery vs SciPy reference values ------------------------------------
TQ = [  # (df, p, scipy t.ppf)
    (1, 0.975, 12.706204736174694),
    (2, 0.95, 2.9199855803537242),
    (8, 0.95, 1.8595480375308973),
    (8, 0.9, 1.3968153097438654),
    (20, 0.975, 2.085963447265864),
    (198, 0.975, 1.9720174778363146),
    (1000, 0.995, 2.580754698065951),
]
PW = [  # (n, d, alpha, two_sided, two_sample, scipy power)
    (2, 1.0, 0.05, True, False, 0.09280915505633609),
    (5, 0.8, 0.05, True, True, 0.2007394526520357),
    (11, 1.0, 0.05, False, False, 0.924489065275314),
    (30, 0.5, 0.05, True, True, 0.47789652076016464),
    (86, 0.5, 0.05, True, True, 0.9032299799904954),
    (200, 0.2, 0.01, True, False, 0.5905710180850182),
    (40, 0.3, 0.10, False, True, 0.5211378477694998),
    (1000, 0.1, 0.05, True, True, 0.6083667058091785),
]


@pytest.mark.parametrize("df,p,ref", TQ)
def test_t_quantile_matches_scipy(df, p, ref):
    assert t_quantile(p, df) == pytest.approx(ref, abs=1e-9)


def test_t_sf_symmetry_and_median():
    assert t_sf(0.0, 7) == pytest.approx(0.5, abs=1e-12)
    assert t_sf(1.3, 7) + t_sf(-1.3, 7) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("n,d,a,two_sided,two_sample,ref", PW)
def test_power_matches_scipy_noncentral_t(n, d, a, two_sided, two_sample, ref):
    assert t_power(n, d, a, two_sided, two_sample) == pytest.approx(ref, abs=1e-7)


# --- Published examples ------------------------------------------------------
def test_minitab_two_sample_example():
    # difference 5, sd 10, alpha .05, power .90 -> n = 86 per group, actual power .903230
    r = compute(Inputs(difference=5, std_dev=10, target_power=0.90))
    assert r.n == 86
    assert r.actual_power == pytest.approx(0.903230, abs=1e-5)
    assert r.total_units == 172


def test_nist_one_sample_example():
    # one-sided, alpha .05, beta .10, delta = sigma: normal formula 8.567 -> 9; t-iteration 10.6 -> 11
    r = compute(Inputs(difference=1, std_dev=1, test_type="one_sample", two_sided=False, target_power=0.90))
    assert r.normal_approx_n == 9
    assert r.n == 11
    # the page's own t-iteration arithmetic: (t_.95,8 + t_.90,8)^2 = 10.6
    assert (t_quantile(0.95, 8) + t_quantile(0.90, 8)) ** 2 == pytest.approx(10.6, abs=0.01)


# --- Properties -------------------------------------------------------------
def test_power_increases_with_n_effect_and_alpha():
    ns = [t_power(n, 0.5, 0.05, True, True) for n in range(2, 60)]
    assert all(b > a for a, b in zip(ns, ns[1:]))
    ds = [t_power(30, d, 0.05, True, True) for d in (0.1, 0.3, 0.5, 0.8)]
    assert ds == sorted(ds)
    al = [t_power(30, 0.5, a, True, True) for a in (0.01, 0.05, 0.10)]
    assert al == sorted(al)


def test_power_at_zero_effect_is_alpha():
    assert t_power(25, 0.0, 0.05, True, True) == pytest.approx(0.05, abs=1e-6)
    assert t_power(25, 0.0, 0.05, False, False) == pytest.approx(0.05, abs=1e-6)


def test_required_n_is_the_smallest_that_meets_target():
    for d, power, two_sample in [(0.5, 0.8, True), (0.8, 0.9, False), (0.3, 0.95, True)]:
        n = required_n(d, 0.05, power, True, two_sample)
        assert t_power(n, d, 0.05, True, two_sample) >= power
        assert t_power(n - 1, d, 0.05, True, two_sample) < power


def test_exact_n_is_close_to_and_not_below_the_normal_limit():
    n_exact = required_n(0.1, 0.05, 0.8, True, False)
    n_norm = normal_approx_n(0.1, 0.05, 0.8, True, False)
    assert 0 <= n_exact - n_norm <= 3


def test_sample_size_scales_with_sd_over_delta_squared():
    a = compute(Inputs(difference=5, std_dev=10)).n
    b = compute(Inputs(difference=5, std_dev=20)).n  # 4x the variance
    assert 3.8 <= b / a <= 4.2


def test_sensitivity_rows_move_the_right_way():
    r = compute(Inputs(difference=5, std_dev=10))
    sd_up, delta_down = r.sensitivity
    assert sd_up.n > r.n and delta_down.n > r.n
    assert delta_down.n > sd_up.n  # 0.8 -> 1/0.64 = 1.56x vs 1.2^2 = 1.44x


def test_table_contains_the_answer_and_power_is_monotone():
    r = compute(Inputs(difference=5, std_dev=10))
    assert any(p.n == r.n for p in r.table)
    pw = [p.power for p in r.table]
    assert pw == sorted(pw)


def test_no_cost_mode_has_no_optimum():
    r = compute(Inputs(difference=5, std_dev=10))
    assert r.optimum is None and all(p.total_cost is None for p in r.table)


# --- Cost tradeoff -----------------------------------------------------------
def worked(**kw):
    args = dict(difference=5, std_dev=10, fixed_cost=2000, unit_cost=150, miss_cost=200000, prob_real=0.5)
    args.update(kw)
    return Inputs(**args)


def test_cost_optimum_matches_brute_force_scan():
    i = worked()
    r = compute(i)
    d = i.difference / i.std_dev
    costs = {}
    for n in range(2, 400):
        p = t_power(n, d, i.alpha, True, True)
        costs[n] = i.fixed_cost + i.unit_cost * 2 * n + i.prob_real * (1 - p) * i.miss_cost
    best = min(costs, key=costs.get)
    assert r.optimum.n == best
    assert r.optimum.total_cost == pytest.approx(costs[best], abs=0.5)


def test_cost_optimum_other_shapes_match_brute_force():
    for kw in [dict(test_type="one_sample", unit_cost=40, miss_cost=50000),
               dict(two_sided=False, miss_cost=20000, prob_real=0.8),
               dict(difference=2.5, miss_cost=500000)]:
        i = worked(**kw)
        r = compute(i)
        d = i.difference / i.std_dev
        units = 2 if i.two_sample else 1
        tot = lambda n: (i.fixed_cost + i.unit_cost * units * n
                         + i.prob_real * (1 - t_power(n, d, i.alpha, i.two_sided, i.two_sample)) * i.miss_cost)
        assert r.optimum.n == min(range(2, 700), key=tot)


def test_cheap_miss_pushes_n_down_and_dear_miss_pushes_it_up():
    low = compute(worked(miss_cost=5000)).optimum.n
    mid = compute(worked()).optimum.n
    high = compute(worked(miss_cost=2_000_000)).optimum.n
    assert low < mid < high


def test_saving_is_nonnegative_and_consistent():
    r = compute(worked())
    o = r.optimum
    assert o.saving_vs_target_n >= -1e-6
    assert o.saving_vs_target_n == pytest.approx(o.target_n_total_cost - o.total_cost)
    assert o.total_cost == pytest.approx(o.testing_cost + o.miss_cost_expected)


# --- Section 7 worked example (SciPy reference, standalone) ------------------
def test_section7_worked_example():
    # delta 5, sd 10, alpha .05 two-sided, F $2,000, $150 per unit (2n units), V $200,000, pi 50%.
    # Expected values from an independent SciPy script, 2026-10-01.
    ref = {40: (0.5981, 54185), 64: (0.8015, 41054), 86: (0.9032, 37477), 89: (0.9126, 37436), 120: (0.9711, 40889)}
    i = worked()
    d = 0.5
    for n, (power, total) in ref.items():
        p = t_power(n, d, 0.05, True, True)
        assert p == pytest.approx(power, abs=1e-4)
        tot = 2000 + 150 * 2 * n + 0.5 * (1 - p) * 200000
        assert tot == pytest.approx(total, abs=1.0)
    r = compute(i)
    assert r.n == 64  # 80% power
    assert r.optimum.n == 89
    assert r.optimum.total_cost == pytest.approx(37436, abs=1.0)
    assert r.optimum.target_n_total_cost == pytest.approx(41054, abs=1.0)
    assert r.optimum.saving_vs_target_n == pytest.approx(3618, abs=1.0)


# --- Validation, entry point -------------------------------------------------
@pytest.mark.parametrize("kw", [
    dict(difference=0, std_dev=10), dict(difference=5, std_dev=0), dict(difference=5, std_dev=10, alpha=0.5),
    dict(difference=5, std_dev=10, target_power=0.3), dict(difference=5, std_dev=10, test_type="paired_x"),
    dict(difference=5, std_dev=10, miss_cost=1000),  # needs a unit cost
    dict(difference=5, std_dev=10, unit_cost=-1), dict(difference=5, std_dev=10, prob_real=0),
])
def test_bad_inputs_rejected(kw):
    with pytest.raises(ValueError):
        Inputs(**kw)


def test_absurd_effect_is_reported_not_hung():
    with pytest.raises(ValueError, match="exceeds"):
        compute(Inputs(difference=0.001, std_dev=100))


def test_compute_from_dict_is_json_serializable():
    out = compute_from_dict(dict(difference=5, std_dev=10, unit_cost=150, miss_cost=200000))
    json.dumps(out)
    assert out["n"] == 64 and out["optimum"]["n"] > 0
