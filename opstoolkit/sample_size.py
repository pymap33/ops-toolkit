"""Sample-size and cost-of-testing planner -- tool 2.1.
Spec: docs/specs/04-sample-size.md.

Sizes a t-test (one-sample/paired, or two independent samples with equal n)
for a stated difference, standard deviation, significance level and power, using
the EXACT t-test power (noncentral t), not the normal approximation. When a cost
per test unit and the cost of missing a real effect are given, it also finds the
n that minimizes total expected cost.

Sources: NIST/SEMATECH e-Handbook of Statistical Methods, section 7.2.2.2 (sample
sizes for a mean test; the t-iteration) and the Minitab "Power and Sample Size
for 2-Sample t" worked example. See docs/validation.md.

The noncentral-t power is computed with the standard library only (numerical
integration over the chi-square variable; central-t quantiles via the
regularized incomplete beta), so it runs in Pyodide with no SciPy. Rates are
decimals: 0.8 means 80%.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

_N = NormalDist()

MAX_N = 100_000
_NEAR_ONE = 1 - 1e-8  # power at which the missed-effect cost is treated as zero


# ---------------------------------------------------------------- t machinery

def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta (modified Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = tiny if abs(d) < tiny else d
    d = 1.0 / d
    h = d
    for m in range(1, 1000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                + a * math.log(x) + b * math.log1p(-x))
    front = math.exp(ln_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_sf(t: float, df: float) -> float:
    """P(T > t) for the central t distribution."""
    tail = 0.5 * _betainc(df / 2.0, 0.5, df / (df + t * t))
    return tail if t >= 0 else 1.0 - tail


def t_quantile(p: float, df: float) -> float:
    """t such that P(T <= t) = p, for 0.5 <= p < 1 (bisection on the survival function)."""
    if not 0.5 <= p < 1.0:
        raise ValueError("t_quantile needs 0.5 <= p < 1")
    target = 1.0 - p
    lo, hi = 0.0, max(10.0, 2.0 * _N.inv_cdf(p))
    while t_sf(hi, df) > target:
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_sf(mid, df) > target:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-13 * max(1.0, hi):
            break
    return 0.5 * (lo + hi)


def _chi2_integral(h, df: float, steps: int = 1500) -> float:
    """E[h(V)] for V ~ chi-square(df), by Simpson's rule in u = sqrt(v).

    The substitution v = u**2 removes the density singularity at 0 for df = 1.
    """
    mu, sd = df, math.sqrt(2.0 * df)
    v_lo = max(0.0, mu - 12.0 * sd) if df > 30 else 0.0
    v_hi = mu + 14.0 * sd + 40.0
    u_lo, u_hi = math.sqrt(v_lo), math.sqrt(v_hi)
    k2 = df / 2.0
    log_norm = -k2 * math.log(2.0) - math.lgamma(k2)
    step = (u_hi - u_lo) / steps
    total = 0.0
    for i in range(steps + 1):
        u = u_lo + i * step
        v = u * u
        if v <= 0.0:
            dens = 0.0 if df > 1 else 2.0 * math.exp(log_norm)  # limit of 2u * v^(k2-1) * ... at u->0
        else:
            dens = 2.0 * u * math.exp((k2 - 1.0) * math.log(v) - v / 2.0 + log_norm)
        w = 1.0 if i in (0, steps) else (4.0 if i % 2 else 2.0)
        total += w * dens * h(v)
    return total * step / 3.0


def t_power(n: int, effect_over_sd: float, alpha: float, two_sided: bool, two_sample: bool,
            steps: int = 1500) -> float:
    """Exact power of the t test at per-group sample size n and standardized effect d = delta/sigma.

    `steps` is the Simpson resolution; 1500 agrees with SciPy to ~2e-9, 400 to ~4e-7 (used for the cost scan).
    """
    if two_sample:
        df, lam = 2 * n - 2, effect_over_sd * math.sqrt(n / 2.0)
    else:
        df, lam = n - 1, effect_over_sd * math.sqrt(n)
    tc = t_quantile(1.0 - (alpha / 2.0 if two_sided else alpha), df)
    root = math.sqrt(df)

    def upper(v: float) -> float:
        return 1.0 - _N.cdf(tc * math.sqrt(v) / root - lam)

    power = _chi2_integral(upper, df, steps)
    if two_sided:
        power += _chi2_integral(lambda v: _N.cdf(-tc * math.sqrt(v) / root - lam), df, steps)
    return min(1.0, max(0.0, power))


# ----------------------------------------------------------------- the planner

@dataclass(frozen=True)
class Inputs:
    difference: float  # delta, measurement units
    std_dev: float  # sigma, measurement units
    test_type: str = "two_sample"  # "one_sample" (also paired) or "two_sample"
    alpha: float = 0.05
    two_sided: bool = True
    target_power: float = 0.80
    fixed_cost: float = 0.0  # $ per study
    unit_cost: float | None = None  # $ per test unit
    miss_cost: float | None = None  # $ value of a real delta-sized effect if missed
    prob_real: float = 0.5

    def __post_init__(self) -> None:
        if self.difference <= 0:
            raise ValueError("difference must be > 0")
        if self.std_dev <= 0:
            raise ValueError("std_dev must be > 0")
        if self.test_type not in ("one_sample", "two_sample"):
            raise ValueError("test_type must be 'one_sample' or 'two_sample'")
        if not 0.001 <= self.alpha <= 0.25:
            raise ValueError("alpha must be between 0.001 and 0.25")
        if not 0.5 <= self.target_power <= 0.999:
            raise ValueError("target_power must be between 50% and 99.9%")
        if self.fixed_cost < 0:
            raise ValueError("fixed_cost must be >= 0")
        if self.unit_cost is not None and self.unit_cost < 0:
            raise ValueError("unit_cost must be >= 0")
        if self.miss_cost is not None and self.miss_cost < 0:
            raise ValueError("miss_cost must be >= 0")
        if not 0.01 <= self.prob_real <= 1.0:
            raise ValueError("prob_real must be between 1% and 100%")
        if self.miss_cost is not None and not self.unit_cost:
            raise ValueError("a cost per test unit > 0 is needed to find the cost-minimizing n")

    @property
    def two_sample(self) -> bool:
        return self.test_type == "two_sample"

    @property
    def units_per_n(self) -> int:
        return 2 if self.two_sample else 1

    @property
    def cost_mode(self) -> bool:
        return self.unit_cost is not None and self.miss_cost is not None


@dataclass(frozen=True)
class PowerPoint:
    n: int
    power: float
    testing_cost: float | None
    miss_cost_expected: float | None
    total_cost: float | None


@dataclass(frozen=True)
class Sensitivity:
    label: str
    n: int


@dataclass(frozen=True)
class CostOptimum:
    n: int
    power: float
    testing_cost: float
    miss_cost_expected: float
    total_cost: float
    target_n_total_cost: float
    saving_vs_target_n: float


@dataclass(frozen=True)
class SampleSizeResult:
    n: int
    actual_power: float
    total_units: int
    effect_size: float  # d = delta / sigma
    normal_approx_n: int
    table: list[PowerPoint]
    sensitivity: list[Sensitivity]
    optimum: CostOptimum | None
    decision: str


def normal_approx_n(d: float, alpha: float, power: float, two_sided: bool, two_sample: bool) -> int:
    """Normal-formula n = (z_(1-a/s) + z_(1-b))^2 / d^2 (x2 for two-sample), rounded up, at least 2."""
    z_a = _N.inv_cdf(1.0 - (alpha / 2.0 if two_sided else alpha))
    n = (z_a + _N.inv_cdf(power)) ** 2 / (d * d) * (2.0 if two_sample else 1.0)
    return max(2, math.ceil(n - 1e-9))


def required_n(d: float, alpha: float, power: float, two_sided: bool, two_sample: bool) -> int:
    """Smallest n (>= 2) whose exact t-test power is >= `power`."""
    def ok(n: int) -> bool:
        return t_power(n, d, alpha, two_sided, two_sample) >= power

    hi = normal_approx_n(d, alpha, power, two_sided, two_sample)
    if hi > MAX_N:
        raise ValueError(f"required sample size exceeds {MAX_N:,} per group; check the difference against the standard deviation")
    while not ok(hi):
        if hi >= MAX_N:
            raise ValueError(f"required sample size exceeds {MAX_N:,} per group; check the difference against the standard deviation")
        hi = min(MAX_N, hi * 2)
    lo = 1  # n = 1 is not a valid test, so treat as failing
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ok(mid):
            hi = mid
        else:
            lo = mid
    return hi


def _costs(i: Inputs, n: int, power: float) -> tuple[float, float, float]:
    testing = i.fixed_cost + i.unit_cost * i.units_per_n * n
    miss = i.prob_real * (1.0 - power) * i.miss_cost
    return testing, miss, testing + miss


def _table_ns(n: int) -> list[int]:
    ns = {max(2, round(n * f)) for f in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0)}
    return sorted(ns | {n})


def _find_optimum(i: Inputs, d: float, n_target: int) -> tuple[int, float]:
    """n minimizing total cost. Past the n where power is ~1 cost only grows, so scan up to there."""
    n_hi = max(n_target, required_n(d, i.alpha, _NEAR_ONE, i.two_sided, i.two_sample))
    cache: dict[int, float] = {}

    def cost(n: int) -> float:
        if n not in cache:
            cache[n] = _costs(i, n, t_power(n, d, i.alpha, i.two_sided, i.two_sample, steps=400))[2]
        return cache[n]

    if n_hi <= 400:
        candidates = range(2, n_hi + 1)
    else:  # coarse grid, then every n around the best coarse point
        stride = max(1, n_hi // 200)
        coarse = list(range(2, n_hi + 1, stride))
        best = min(coarse, key=cost)
        candidates = range(max(2, best - stride), min(n_hi, best + stride) + 1)
    best_n = min(candidates, key=cost)
    return best_n, cache[best_n]


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _decision(i: Inputs, n: int, power: float, units: int, opt: CostOptimum | None) -> str:
    per = " per group" if i.two_sample else ""
    base = (f"To detect a difference of {i.difference:g} (standard deviation {i.std_dev:g}) with "
            f"{i.target_power * 100:.0f}% power at α = {i.alpha:g}, test {n}{per} ({units} units in all); "
            f"actual power {power * 100:.1f}%.")
    if opt is None:
        return base + " Add a cost per unit and the cost of missing a real effect to find the cost-minimizing n."
    if opt.n == n:
        return base + f" That is also the cost-minimizing n (expected total cost {_money(opt.total_cost)})."
    direction = "more" if opt.n > n else "fewer"
    return (base + f" The cost-minimizing n is {opt.n}{per} ({abs(opt.n - n)} {direction}; power "
            f"{opt.power * 100:.1f}%), which lowers expected total cost from {_money(opt.target_n_total_cost)} "
            f"to {_money(opt.total_cost)}, a saving of {_money(opt.saving_vs_target_n)}.")


def compute(i: Inputs) -> SampleSizeResult:
    d = i.difference / i.std_dev
    n = required_n(d, i.alpha, i.target_power, i.two_sided, i.two_sample)
    power = t_power(n, d, i.alpha, i.two_sided, i.two_sample)

    optimum = None
    n_opt = None
    if i.cost_mode:
        n_opt, _ = _find_optimum(i, d, n)

    table = []
    for m in sorted(set(_table_ns(n)) | ({n_opt} if n_opt else set())):
        p = power if m == n else t_power(m, d, i.alpha, i.two_sided, i.two_sample)
        if i.cost_mode:
            t, miss, tot = _costs(i, m, p)
            table.append(PowerPoint(m, p, t, miss, tot))
        else:
            table.append(PowerPoint(m, p, None, None, None))

    sens = [
        Sensitivity("Standard deviation 20% larger", required_n(d / 1.2, i.alpha, i.target_power, i.two_sided, i.two_sample)),
        Sensitivity("Difference 20% smaller", required_n(d * 0.8, i.alpha, i.target_power, i.two_sided, i.two_sample)),
    ]

    if i.cost_mode:
        p_opt = t_power(n_opt, d, i.alpha, i.two_sided, i.two_sample)
        t_opt, miss_opt, total_opt = _costs(i, n_opt, p_opt)
        target_total = _costs(i, n, power)[2]
        optimum = CostOptimum(
            n=n_opt, power=p_opt, testing_cost=t_opt, miss_cost_expected=miss_opt, total_cost=total_opt,
            target_n_total_cost=target_total, saving_vs_target_n=target_total - total_opt,
        )

    units = n * i.units_per_n
    return SampleSizeResult(
        n=n, actual_power=power, total_units=units, effect_size=d,
        normal_approx_n=normal_approx_n(d, i.alpha, i.target_power, i.two_sided, i.two_sample),
        table=table, sensitivity=sens, optimum=optimum,
        decision=_decision(i, n, power, units, optimum),
    )


def compute_from_dict(payload: dict) -> dict:
    """JSON-friendly entry point used by the browser page."""
    from dataclasses import asdict

    return asdict(compute(Inputs(**payload)))
