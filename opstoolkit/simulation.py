"""Shared simulation helpers -- plan item 0.6 (prerequisite for the Monte Carlo tools).
Spec: docs/specs/06-simulation-helpers.md.

One tested home for randomness: a seeded RNG, input distributions (uniform, triangular,
modified PERT, normal with optional truncation, lognormal given its arithmetic mean and
sd, fixed), a `simulate` runner, and percentile/summary helpers. Inputs are drawn
independently (no correlation in v1). Output is only as good as the input ranges: results
are scenario ranges, not forecasts.

Every distribution exposes mean, variance, cdf(x), ppf(p) and sample(rng). Expected
values in the tests come from scripts/simulation_reference_values.py (SciPy, reference
only); this module uses only the standard library.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import NormalDist
from typing import Callable

from opstoolkit.special import betainc

MAX_N = 200_000
DEFAULT_N = 10_000
_N01 = NormalDist()


def make_rng(seed: int) -> random.Random:
    """A seeded generator. Same seed, same inputs -> identical results."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    return random.Random(seed)


def _finite(name: str, x: float) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f"{name} must be a finite number")
    return float(x)


def _check_p(p: float) -> float:
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be between 0 and 1")
    return p


def _bisect_ppf(cdf: Callable[[float], float], p: float, lo: float, hi: float) -> float:
    """Invert a monotone cdf on [lo, hi] by bisection (to ~1e-13 of the range)."""
    if p <= 0.0:
        return lo
    if p >= 1.0:
        return hi
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if cdf(mid) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-14 * max(1.0, abs(hi)):
            break
    return 0.5 * (lo + hi)


# ------------------------------------------------------------- distributions

@dataclass(frozen=True)
class Fixed:
    value: float

    def __post_init__(self) -> None:
        _finite("Fixed value", self.value)

    @property
    def mean(self) -> float:
        return self.value

    @property
    def variance(self) -> float:
        return 0.0

    def cdf(self, x: float) -> float:
        return 1.0 if x >= self.value else 0.0

    def ppf(self, p: float) -> float:
        _check_p(p)
        return self.value

    def sample(self, rng: random.Random) -> float:
        return self.value


@dataclass(frozen=True)
class Uniform:
    low: float
    high: float

    def __post_init__(self) -> None:
        _finite("Uniform low", self.low)
        _finite("Uniform high", self.high)
        if not self.low < self.high:
            raise ValueError("Uniform: low must be less than high")

    @property
    def mean(self) -> float:
        return 0.5 * (self.low + self.high)

    @property
    def variance(self) -> float:
        return (self.high - self.low) ** 2 / 12.0

    def cdf(self, x: float) -> float:
        return min(1.0, max(0.0, (x - self.low) / (self.high - self.low)))

    def ppf(self, p: float) -> float:
        _check_p(p)
        return self.low + p * (self.high - self.low)

    def sample(self, rng: random.Random) -> float:
        return self.ppf(rng.random())


@dataclass(frozen=True)
class Triangular:
    low: float
    mode: float
    high: float

    def __post_init__(self) -> None:
        for n, v in (("low", self.low), ("mode", self.mode), ("high", self.high)):
            _finite(f"Triangular {n}", v)
        if not self.low <= self.mode <= self.high:
            raise ValueError("Triangular: need low <= mode <= high")
        if self.low == self.high:
            raise ValueError("Triangular: low and high must differ (use Fixed for a point)")

    @property
    def mean(self) -> float:
        return (self.low + self.mode + self.high) / 3.0

    @property
    def variance(self) -> float:
        a, c, b = self.low, self.mode, self.high
        return (a * a + b * b + c * c - a * b - a * c - b * c) / 18.0

    def cdf(self, x: float) -> float:
        a, c, b = self.low, self.mode, self.high
        if x <= a:
            return 0.0
        if x >= b:
            return 1.0
        if x <= c:
            return (x - a) ** 2 / ((b - a) * (c - a))
        return 1.0 - (b - x) ** 2 / ((b - a) * (b - c))

    def ppf(self, p: float) -> float:
        _check_p(p)
        a, c, b = self.low, self.mode, self.high
        split = (c - a) / (b - a)
        if p < split:
            return a + math.sqrt(p * (b - a) * (c - a))
        return b - math.sqrt((1.0 - p) * (b - a) * (b - c))

    def sample(self, rng: random.Random) -> float:
        return self.ppf(rng.random())


@dataclass(frozen=True)
class PERT:
    """Modified PERT: a beta on [low, high] with mean (low + lam*mode + high)/(lam + 2)."""
    low: float
    mode: float
    high: float
    lam: float = 4.0

    def __post_init__(self) -> None:
        for n, v in (("low", self.low), ("mode", self.mode), ("high", self.high),
                     ("lam", self.lam)):
            _finite(f"PERT {n}", v)
        if not self.low <= self.mode <= self.high:
            raise ValueError("PERT: need low <= mode <= high")
        if self.low == self.high:
            raise ValueError("PERT: low and high must differ (use Fixed for a point)")
        if self.lam <= 0:
            raise ValueError("PERT: lam must be > 0")

    @property
    def alpha(self) -> float:
        return 1.0 + self.lam * (self.mode - self.low) / (self.high - self.low)

    @property
    def beta(self) -> float:
        return 1.0 + self.lam * (self.high - self.mode) / (self.high - self.low)

    @property
    def mean(self) -> float:
        return (self.low + self.lam * self.mode + self.high) / (self.lam + 2.0)

    @property
    def variance(self) -> float:
        a, b = self.alpha, self.beta
        return (self.high - self.low) ** 2 * a * b / ((a + b) ** 2 * (a + b + 1.0))

    def cdf(self, x: float) -> float:
        z = (x - self.low) / (self.high - self.low)
        return betainc(self.alpha, self.beta, z)

    def ppf(self, p: float) -> float:
        _check_p(p)
        return _bisect_ppf(self.cdf, p, self.low, self.high)

    def sample(self, rng: random.Random) -> float:
        return self.low + (self.high - self.low) * rng.betavariate(self.alpha, self.beta)


@dataclass(frozen=True)
class Normal:
    """Normal(mean, sd), optionally truncated to [lo, hi] (sampled by inverse cdf, so
    there is no rejection loop; mean and variance are those of the truncated variable)."""
    mu: float
    sd: float
    lo: float | None = None
    hi: float | None = None

    def __post_init__(self) -> None:
        _finite("Normal mean", self.mu)
        _finite("Normal sd", self.sd)
        if self.sd <= 0:
            raise ValueError("Normal: sd must be > 0")
        for n, v in (("lo", self.lo), ("hi", self.hi)):
            if v is not None:
                _finite(f"Normal {n}", v)
        if self.lo is not None and self.hi is not None and not self.lo < self.hi:
            raise ValueError("Normal: lo must be less than hi")
        if self._mass() < 1e-12:
            raise ValueError("Normal: truncation leaves essentially no probability mass")

    def _z(self, x: float) -> float:
        return (x - self.mu) / self.sd

    @property
    def _fa(self) -> float:
        return 0.0 if self.lo is None else _N01.cdf(self._z(self.lo))

    @property
    def _fb(self) -> float:
        return 1.0 if self.hi is None else _N01.cdf(self._z(self.hi))

    def _mass(self) -> float:
        return self._fb - self._fa

    def _moment_terms(self) -> tuple[float, float]:
        """phi at the bounds times the bound's z (0 when unbounded): returns (dphi, dzphi)."""
        pa = pb = za = zb = 0.0
        if self.lo is not None:
            za = self._z(self.lo)
            pa = _N01.pdf(za)
        if self.hi is not None:
            zb = self._z(self.hi)
            pb = _N01.pdf(zb)
        return pa - pb, za * pa - zb * pb

    @property
    def mean(self) -> float:
        dphi, _ = self._moment_terms()
        return self.mu + self.sd * dphi / self._mass()

    @property
    def variance(self) -> float:
        dphi, dzphi = self._moment_terms()
        m = self._mass()
        return self.sd ** 2 * (1.0 + dzphi / m - (dphi / m) ** 2)

    def cdf(self, x: float) -> float:
        if self.lo is not None and x <= self.lo:
            return 0.0
        if self.hi is not None and x >= self.hi:
            return 1.0
        return (_N01.cdf(self._z(x)) - self._fa) / self._mass()

    def ppf(self, p: float) -> float:
        _check_p(p)
        if self.lo is None and self.hi is None:
            if p <= 0.0 or p >= 1.0:
                raise ValueError("Normal: ppf is infinite at p = 0 or 1 (give truncation bounds)")
            return self.mu + self.sd * _N01.inv_cdf(p)
        if p <= 0.0 and self.lo is not None:
            return self.lo
        if p >= 1.0 and self.hi is not None:
            return self.hi
        q = min(max(self._fa + p * self._mass(), 1e-300), 1.0 - 1e-16)
        x = self.mu + self.sd * _N01.inv_cdf(q)
        if self.lo is not None:
            x = max(x, self.lo)
        if self.hi is not None:
            x = min(x, self.hi)
        return x

    def sample(self, rng: random.Random) -> float:
        if self.lo is None and self.hi is None:
            return rng.gauss(self.mu, self.sd)
        return self.ppf(rng.random())


@dataclass(frozen=True)
class LogNormal:
    """Lognormal given the ARITHMETIC mean and sd of the variable itself (what a user
    means by "about 50, give or take 20"); underlying mu, sigma are derived."""
    mean_: float
    sd: float

    def __post_init__(self) -> None:
        _finite("LogNormal mean", self.mean_)
        _finite("LogNormal sd", self.sd)
        if self.mean_ <= 0:
            raise ValueError("LogNormal: mean must be > 0")
        if self.sd <= 0:
            raise ValueError("LogNormal: sd must be > 0")

    @property
    def sigma(self) -> float:
        return math.sqrt(math.log1p((self.sd / self.mean_) ** 2))

    @property
    def mu(self) -> float:
        return math.log(self.mean_) - 0.5 * self.sigma ** 2

    @property
    def mean(self) -> float:
        return self.mean_

    @property
    def variance(self) -> float:
        return self.sd ** 2

    def cdf(self, x: float) -> float:
        if x <= 0:
            return 0.0
        return _N01.cdf((math.log(x) - self.mu) / self.sigma)

    def ppf(self, p: float) -> float:
        _check_p(p)
        if p <= 0.0:
            return 0.0
        if p >= 1.0:
            raise ValueError("LogNormal: ppf is infinite at p = 1")
        return math.exp(self.mu + self.sigma * _N01.inv_cdf(p))

    def sample(self, rng: random.Random) -> float:
        return rng.lognormvariate(self.mu, self.sigma)


# ------------------------------------------------------------------- runner

def dist_from_dict(spec: dict):
    """Build a distribution from JSON-style input, for the page bridge.
    {"type": "pert", "low": 1, "mode": 2, "high": 5} etc."""
    if not isinstance(spec, dict) or "type" not in spec:
        raise ValueError("a distribution spec needs a 'type'")
    t = str(spec["type"]).lower()
    try:
        if t == "fixed":
            return Fixed(spec["value"])
        if t == "uniform":
            return Uniform(spec["low"], spec["high"])
        if t == "triangular":
            return Triangular(spec["low"], spec["mode"], spec["high"])
        if t == "pert":
            return PERT(spec["low"], spec["mode"], spec["high"], spec.get("lam", 4.0))
        if t == "normal":
            return Normal(spec["mean"], spec["sd"], spec.get("lo"), spec.get("hi"))
        if t == "lognormal":
            return LogNormal(spec["mean"], spec["sd"])
    except KeyError as e:
        raise ValueError(f"{t} distribution is missing {e.args[0]!r}") from None
    raise ValueError(f"unknown distribution type '{t}'")


@dataclass(frozen=True)
class SimResult:
    results: list[float]
    draws: dict[str, list[float]]  # input name -> its drawn values, for sensitivity work


def simulate(model: Callable[[dict], float], inputs: dict, n: int = DEFAULT_N,
             seed: int = 1) -> SimResult:
    """Draw every input independently, n times, and evaluate model({name: value})."""
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_N:
        raise ValueError(f"n must be an integer from 1 to {MAX_N}")
    if not inputs:
        raise ValueError("simulate needs at least one input")
    rng = make_rng(seed)
    names = list(inputs)
    draws: dict[str, list[float]] = {k: [] for k in names}
    results: list[float] = []
    for _ in range(n):
        row = {k: inputs[k].sample(rng) for k in names}
        for k in names:
            draws[k].append(row[k])
        results.append(float(model(row)))
    return SimResult(results, draws)


# ---------------------------------------------------------------- summaries

def percentile(xs: list[float], p: float) -> float:
    """p in [0, 100]; linear interpolation between order statistics (NumPy's default)."""
    if not xs:
        raise ValueError("percentile of an empty list")
    if not 0.0 <= p <= 100.0:
        raise ValueError("p must be between 0 and 100")
    s = sorted(xs)
    h = (len(s) - 1) * p / 100.0
    lo = math.floor(h)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def prob_below(xs: list[float], threshold: float) -> float:
    """Share of results strictly below the threshold."""
    if not xs:
        raise ValueError("empty list")
    return sum(1 for x in xs if x < threshold) / len(xs)


def prob_above(xs: list[float], threshold: float) -> float:
    """Share of results strictly above the threshold."""
    if not xs:
        raise ValueError("empty list")
    return sum(1 for x in xs if x > threshold) / len(xs)


def summarize(xs: list[float]) -> dict:
    """Mean, sample sd (0 for one value), min, max, P10, P50, P90."""
    if not xs:
        raise ValueError("summarize of an empty list")
    n = len(xs)
    mean = math.fsum(xs) / n
    sd = math.sqrt(math.fsum((x - mean) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
    return {
        "n": n, "mean": mean, "sd": sd, "min": min(xs), "max": max(xs),
        "p10": percentile(xs, 10), "p50": percentile(xs, 50), "p90": percentile(xs, 90),
    }
