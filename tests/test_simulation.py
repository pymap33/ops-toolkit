"""Tests for opstoolkit/simulation.py (plan item 0.6).

Expected literals come from scripts/simulation_reference_values.py (SciPy/NumPy, run
independently of the library), or from hand arithmetic noted inline. Stochastic checks
use fixed seeds and tolerances written in standard errors (SE), so they cannot flake
and would still pass in expectation under a different seed.
"""

import math

import pytest

from opstoolkit.simulation import (
    PERT, Fixed, LogNormal, Normal, Triangular, Uniform, dist_from_dict, make_rng,
    percentile, prob_above, prob_below, simulate, summarize, MAX_N,
)

N = 200_000
Z = 4.0  # tolerance in standard errors

# name: (distribution, mean, variance, P10, P50, P90)  -- all from the SciPy script
CASES = {
    "uniform": (Uniform(2, 10), 6.0, 5.3333333333, 2.8, 6.0, 9.2),
    "tri_10_12_20": (Triangular(10, 12, 20), 14.0, 4.6666666667,
                     11.4142135624, 13.6754446797, 17.1715728753),
    "tri_0_9_10": (Triangular(0, 9, 10), 6.3333333333, 5.0555555556,
                   3.0, 6.7082039325, 9.0),
    "pert_10_12_20": (PERT(10, 12, 20), 13.0, 3.0,
                      10.8990213046, 12.7667225939, 15.4533405043),
    "pert_0_1_10": (PERT(0, 1, 10), 2.3333333333, 2.5555555556,
                    0.5079277567, 2.0266485036, 4.6232974996),
    "normal": (Normal(100, 15), 100.0, 225.0, 80.7767265168, 100.0, 119.2232734832),
    "lognormal": (LogNormal(50, 20), 50.0, 400.0,
                  28.3348132701, 46.4238345443, 76.0609358266),
    "trunc_both": (Normal(100, 15, 90, 130), 105.4940535508, 95.1777000171,
                   93.1922447487, 104.3805695201, 119.6386592095),
    "trunc_hi": (Normal(100, 15, None, 110), 93.5897361250, 119.8058783035,
                 78.3805820767, 95.1710843943, 106.7130718643),
    "trunc_lo": (Normal(100, 15, 95, None), 108.9773541720, 99.5203412110,
                 97.4497000841, 107.2141101920, 122.9442445249),
}


def draws(dist, seed=12345, n=N):
    rng = make_rng(seed)
    return [dist.sample(rng) for _ in range(n)]


# --------------------------------------------------- analytic properties (no sampling)

@pytest.mark.parametrize("name", CASES)
def test_analytic_mean_variance_and_quantiles(name):
    d, mean, var, p10, p50, p90 = CASES[name]
    assert d.mean == pytest.approx(mean, rel=1e-9)
    assert d.variance == pytest.approx(var, rel=1e-9)
    for p, want in ((0.1, p10), (0.5, p50), (0.9, p90)):
        assert d.ppf(p) == pytest.approx(want, rel=1e-8, abs=1e-8)


@pytest.mark.parametrize("name", CASES)
def test_cdf_ppf_round_trip(name):
    d = CASES[name][0]
    for p in [0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 0.999]:
        assert d.cdf(d.ppf(p)) == pytest.approx(p, abs=1e-9)


def test_cdf_reference_values():
    assert Triangular(10, 12, 20).cdf(15.0) == pytest.approx(0.6875, abs=1e-12)
    assert PERT(10, 12, 20).cdf(13.0) == pytest.approx(0.548230304262, abs=1e-9)
    assert Normal(100, 15).cdf(110.0) == pytest.approx(0.747507462453, abs=1e-9)
    assert LogNormal(50, 20).cdf(60.0) == pytest.approx(0.747255415859, abs=1e-9)
    assert Uniform(2, 10).cdf(3.0) == pytest.approx(0.125, abs=1e-12)
    assert Normal(100, 15, 90, 130).cdf(100.0) == pytest.approx(0.341503910393, abs=1e-9)
    assert Normal(100, 15, None, 110).cdf(100.0) == pytest.approx(0.668889643401, abs=1e-9)
    assert Normal(100, 15, 95, None).cdf(100.0) == pytest.approx(0.207052361878, abs=1e-9)


def test_cdf_outside_support():
    t = Triangular(10, 12, 20)
    assert t.cdf(5) == 0.0 and t.cdf(25) == 1.0
    assert Uniform(2, 10).cdf(-1) == 0.0 and Uniform(2, 10).cdf(11) == 1.0
    assert LogNormal(50, 20).cdf(0) == 0.0 and LogNormal(50, 20).cdf(-3) == 0.0
    tn = Normal(100, 15, 90, 130)
    assert tn.cdf(80) == 0.0 and tn.cdf(140) == 1.0


def test_hand_arithmetic_worked_example():
    # Spec section 7. Triangular(10,12,20): variance (100+400+144-200-120-240)/18 = 84/18;
    # P50 = 20 - sqrt(0.5*10*8). PERT(10,12,20): mean (10+48+20)/6; var (13-10)(20-13)/7.
    t = Triangular(10, 12, 20)
    assert t.variance == pytest.approx(84 / 18)
    assert t.ppf(0.5) == pytest.approx(20 - math.sqrt(40))
    p = PERT(10, 12, 20)
    assert p.mean == pytest.approx(78 / 6)
    assert p.variance == pytest.approx(3 * 7 / 7)
    assert p.variance < t.variance  # PERT is the tighter of the two


def test_lognormal_parameter_conversion():
    d = LogNormal(50, 20)
    assert d.mu == pytest.approx(3.8378130029, abs=1e-9)
    assert d.sigma == pytest.approx(0.3852531702, abs=1e-9)


def test_pert_symmetric_and_lam_one_is_flat_beta():
    s = PERT(0, 5, 10)
    assert s.mean == pytest.approx(5.0) and s.ppf(0.5) == pytest.approx(5.0, abs=1e-9)
    # lam = 2 with mode in the middle -> Beta(2,2); variance (b-a)^2 / 20
    assert PERT(0, 5, 10, lam=2).variance == pytest.approx(100 / 20)


def test_fixed():
    f = Fixed(7.5)
    assert f.mean == 7.5 and f.variance == 0.0 and f.ppf(0.3) == 7.5
    assert f.cdf(7.4) == 0.0 and f.cdf(7.5) == 1.0
    assert f.sample(make_rng(1)) == 7.5


# ------------------------------------------------------------ sampling vs analytic

def _sample_stats(xs):
    n = len(xs)
    mean = math.fsum(xs) / n
    var = math.fsum((x - mean) ** 2 for x in xs) / (n - 1)
    m4 = math.fsum((x - mean) ** 4 for x in xs) / n
    se_mean = math.sqrt(var / n)
    se_var = math.sqrt(max(m4 - var * var, 0.0) / n)  # SE of the sample variance
    return mean, var, se_mean, se_var


@pytest.mark.parametrize("name", CASES)
def test_sample_moments_within_standard_errors(name):
    d, mean, var, *_ = CASES[name]
    xs = draws(d)
    m, v, se_m, se_v = _sample_stats(xs)
    assert abs(m - mean) < Z * se_m
    assert abs(v - var) < Z * se_v


@pytest.mark.parametrize("name", CASES)
def test_sample_percentiles_within_standard_errors(name):
    d, _, _, p10, p50, p90 = CASES[name]
    xs = draws(d)
    for p, want in ((10, p10), (50, p50), (90, p90)):
        q = p / 100
        h = 1e-4 * (d.ppf(0.99) - d.ppf(0.01))
        dens = (d.cdf(want + h) - d.cdf(want - h)) / (2 * h)  # density at the quantile
        se = math.sqrt(q * (1 - q) / N) / dens
        assert abs(percentile(xs, p) - want) < Z * se


def test_samples_stay_in_support():
    for name in ("uniform", "tri_10_12_20", "pert_10_12_20", "trunc_both", "trunc_hi", "trunc_lo"):
        d = CASES[name][0]
        xs = draws(d, n=20_000)
        lo = getattr(d, "low", getattr(d, "lo", None))
        hi = getattr(d, "high", getattr(d, "hi", None))
        if lo is not None:
            assert min(xs) >= lo
        if hi is not None:
            assert max(xs) <= hi
    assert min(draws(LogNormal(50, 20), n=20_000)) > 0


# ------------------------------------------------------------ determinism / runner

def test_same_seed_identical_different_seed_different():
    inputs = {"a": PERT(1, 2, 5), "b": Normal(10, 2)}
    f = lambda v: v["a"] * v["b"]
    r1 = simulate(f, inputs, n=500, seed=7)
    r2 = simulate(f, inputs, n=500, seed=7)
    r3 = simulate(f, inputs, n=500, seed=8)
    assert r1.results == r2.results and r1.draws == r2.draws
    assert r1.results != r3.results


def test_simulate_records_draws_and_applies_model():
    r = simulate(lambda v: v["a"] + 2 * v["b"], {"a": Uniform(0, 1), "b": Fixed(3.0)}, n=100, seed=3)
    assert len(r.results) == 100 and set(r.draws) == {"a", "b"}
    for res, a, b in zip(r.results, r.draws["a"], r.draws["b"]):
        assert res == pytest.approx(a + 2 * b) and b == 3.0


def test_inputs_are_independent():
    r = simulate(lambda v: 0.0, {"x": Normal(0, 1), "y": Normal(0, 1)}, n=50_000, seed=99)
    x, y = r.draws["x"], r.draws["y"]
    mx, my = math.fsum(x) / len(x), math.fsum(y) / len(y)
    cov = math.fsum((a - mx) * (b - my) for a, b in zip(x, y)) / (len(x) - 1)
    corr = cov / (math.sqrt(math.fsum((a - mx) ** 2 for a in x) / (len(x) - 1))
                  * math.sqrt(math.fsum((b - my) ** 2 for b in y) / (len(y) - 1)))
    assert abs(corr) < 4 / math.sqrt(len(x))


def test_composition_sum_of_normals():
    # X ~ N(10, 2), Y ~ N(30, 5): X + Y ~ N(40, sqrt(4 + 25)) by hand.
    r = simulate(lambda v: v["x"] + v["y"], {"x": Normal(10, 2), "y": Normal(30, 5)},
                 n=100_000, seed=2024)
    m, v, se_m, se_v = _sample_stats(r.results)
    assert abs(m - 40.0) < Z * se_m
    assert abs(v - 29.0) < Z * se_v
    s = summarize(r.results)
    # P10/P90 of N(40, sqrt(29)): 40 -/+ 1.2815515655 * 5.385164807
    assert s["p10"] == pytest.approx(40 - 1.2815515655 * math.sqrt(29), abs=Z * math.sqrt(29) / 100_000 ** 0.5 * 1.8)
    assert s["p90"] == pytest.approx(40 + 1.2815515655 * math.sqrt(29), abs=Z * math.sqrt(29) / 100_000 ** 0.5 * 1.8)


# ------------------------------------------------------------------- summaries

@pytest.mark.parametrize("arr, want", [
    ([5.0], [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]),
    ([1.0, 2.0], [1.0, 1.1, 1.25, 1.5, 1.9, 2.0]),
    ([3, 1, 2, 2, 9, 7, 7, 4], [1.0, 1.7, 2.0, 3.5, 7.6, 9.0]),   # ties, unsorted
    (list(range(1, 12)), [1.0, 2.0, 3.5, 6.0, 10.0, 11.0]),
])
def test_percentile_matches_numpy_default(arr, want):
    got = [percentile(arr, p) for p in (0, 10, 25, 50, 90, 100)]
    assert got == pytest.approx(want, abs=1e-12)


def test_percentile_does_not_mutate_input():
    a = [3, 1, 2]
    percentile(a, 50)
    assert a == [3, 1, 2]


def test_summarize_and_probabilities():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    s = summarize(xs)
    assert s["mean"] == 3.0 and s["min"] == 1.0 and s["max"] == 5.0 and s["n"] == 5
    assert s["sd"] == pytest.approx(math.sqrt(2.5))  # sample sd, hand: sum sq dev 10 / 4
    assert s["p50"] == 3.0
    assert prob_below(xs, 3.0) == 0.4 and prob_above(xs, 3.0) == 0.4  # strict
    assert summarize([4.0])["sd"] == 0.0


# --------------------------------------------------------------- validation errors

@pytest.mark.parametrize("make", [
    lambda: Uniform(5, 5), lambda: Uniform(6, 5),
    lambda: Triangular(1, 0, 5), lambda: Triangular(1, 6, 5), lambda: Triangular(2, 2, 2),
    lambda: PERT(1, 0, 5), lambda: PERT(1, 2, 5, lam=0), lambda: PERT(1, 2, 5, lam=-1),
    lambda: PERT(3, 3, 3),
    lambda: Normal(0, 0), lambda: Normal(0, -1), lambda: Normal(0, 1, 5, 5),
    lambda: Normal(0, 1, 6, 5), lambda: Normal(0, 1, 50, 60),  # no mass
    lambda: LogNormal(0, 1), lambda: LogNormal(-5, 1), lambda: LogNormal(5, 0),
    lambda: Fixed(float("nan")), lambda: Uniform(float("inf"), 1), lambda: Uniform("a", 5),
    lambda: Uniform(True, 5),
])
def test_bad_parameters_raise(make):
    with pytest.raises(ValueError):
        make()


def test_bad_arguments_raise():
    d = Uniform(0, 1)
    with pytest.raises(ValueError):
        d.ppf(1.5)
    with pytest.raises(ValueError):
        Normal(0, 1).ppf(0.0)  # infinite without truncation
    with pytest.raises(ValueError):
        LogNormal(5, 1).ppf(1.0)
    for n in (0, -1, MAX_N + 1, 1.5, True, "5"):
        with pytest.raises(ValueError):
            simulate(lambda v: 0.0, {"a": d}, n=n)
    with pytest.raises(ValueError):
        simulate(lambda v: 0.0, {}, n=10)
    with pytest.raises(ValueError):
        make_rng(1.5)
    for fn in (percentile, summarize):
        with pytest.raises(ValueError):
            fn([]) if fn is summarize else fn([], 50)
    with pytest.raises(ValueError):
        percentile([1, 2], 101)


def test_dist_from_dict():
    assert dist_from_dict({"type": "PERT", "low": 1, "mode": 2, "high": 5}) == PERT(1, 2, 5)
    assert dist_from_dict({"type": "pert", "low": 1, "mode": 2, "high": 5, "lam": 6}).lam == 6
    assert dist_from_dict({"type": "triangular", "low": 1, "mode": 2, "high": 5}) == Triangular(1, 2, 5)
    assert dist_from_dict({"type": "normal", "mean": 0, "sd": 1, "lo": -1, "hi": 1}) == Normal(0, 1, -1, 1)
    assert dist_from_dict({"type": "lognormal", "mean": 5, "sd": 2}) == LogNormal(5, 2)
    assert dist_from_dict({"type": "uniform", "low": 0, "high": 1}) == Uniform(0, 1)
    assert dist_from_dict({"type": "fixed", "value": 3}) == Fixed(3)
    for bad in ({}, {"type": "weibull"}, {"type": "pert", "low": 1}, "pert", None):
        with pytest.raises(ValueError):
            dist_from_dict(bad)
