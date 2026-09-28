"""Make-vs-buy / total cost of ownership (TCO) model -- tool 2.2.
Spec: docs/specs/02-make-vs-buy.md.

Compares two options on total annual cost, TCO-adjusted: fixed cost, annualized
one-time cost, variable cost with quality, inventory-carrying and risk adders.
Every term is linear in volume, so the comparison is a straight-line break-even:
Q* = (F_a - F_b) / (v_b - v_a). Framework source: eCampusOntario,
"Fundamentals of Operations Management", section 4.10 (make-or-buy break-even).

Rates (defect_rate, carrying_rate, risk_premium, discount_rate) are decimals:
0.05 means 5%. "Option A" is conventionally Make, "Option B" is Buy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

# Cost-by-volume table and sensitivity axes (spec section 4).
VOLUME_FACTORS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
SENSITIVITY_DELTAS = (-0.20, 0.0, 0.20)


@dataclass(frozen=True)
class Option:
    name: str
    fixed_annual: float
    variable_per_unit: float
    one_time: float = 0.0
    defect_rate: float = 0.0
    cost_per_defect: float = 0.0
    inventory_days: float = 0.0
    carrying_rate: float = 0.20
    risk_premium: float = 0.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("every option needs a name")
        for label in ("fixed_annual", "variable_per_unit", "one_time", "cost_per_defect",
                      "inventory_days", "carrying_rate", "risk_premium"):
            if getattr(self, label) < 0:
                raise ValueError(f"{self.name!r}: {label} must be >= 0")
        if not 0.0 <= self.defect_rate <= 1.0:
            raise ValueError(f"{self.name!r}: defect_rate must be between 0 and 1")


@dataclass(frozen=True)
class OptionResult:
    name: str
    effective_fixed: float
    effective_variable: float
    total_cost: float
    cost_per_unit: float | None  # None at zero volume


@dataclass(frozen=True)
class BreakEven:
    """kind: "crossover" (one crossing at volume > 0), "dominated" (one option is
    cheaper at every positive volume), "parallel" (equal variable cost, different
    fixed) or "identical" (same cost curve)."""

    kind: str
    volume: float | None
    cheaper_above: str | None
    cheaper_below: str | None
    cheaper_everywhere: str | None


@dataclass(frozen=True)
class MakeVsBuyResult:
    volume: float
    options: tuple[OptionResult, OptionResult]
    preferred: str | None  # None = tie
    advantage: float  # annual $, >= 0
    advantage_pct: float | None  # of the costlier option's total
    break_even: BreakEven
    naive_options: tuple[OptionResult, OptionResult]
    naive_preferred: str | None
    naive_break_even: BreakEven
    volume_table: list[dict]
    sensitivity: dict  # {"buy_delta": [...], "make_delta": [...], "break_even": [[...]]}
    decision: str


def capital_recovery_factor(rate: float, years: int) -> float:
    """Annual payment per $1 of one-time cost spread over `years` at `rate`."""
    if rate == 0:
        return 1.0 / years
    return rate / (1 - (1 + rate) ** -years)


def effective_fixed(o: Option, rate: float, years: int) -> float:
    return o.fixed_annual + o.one_time * capital_recovery_factor(rate, years)


def effective_variable(o: Option) -> float:
    return (o.variable_per_unit * (1 + o.risk_premium + o.inventory_days / 365 * o.carrying_rate)
            + o.defect_rate * o.cost_per_defect)


def _break_even(fa: float, va: float, fb: float, vb: float, name_a: str, name_b: str) -> BreakEven:
    dv = vb - va
    df = fa - fb
    if math.isclose(dv, 0.0, abs_tol=1e-12):
        if math.isclose(df, 0.0, abs_tol=1e-9):
            return BreakEven("identical", None, None, None, None)
        return BreakEven("parallel", None, None, None, name_a if df < 0 else name_b)
    lower_variable = name_a if dv > 0 else name_b
    higher_variable = name_b if dv > 0 else name_a
    q_star = df / dv
    if q_star <= 0:
        return BreakEven("dominated", None, None, None, lower_variable)
    return BreakEven("crossover", q_star, lower_variable, higher_variable, None)


def _result(o: Option, fixed: float, variable: float, volume: float) -> OptionResult:
    total = fixed + variable * volume
    return OptionResult(o.name, fixed, variable, total, total / volume if volume else None)


def _preferred(a: OptionResult, b: OptionResult) -> str | None:
    if math.isclose(a.total_cost, b.total_cost, rel_tol=1e-12, abs_tol=1e-9):
        return None
    return a.name if a.total_cost < b.total_cost else b.name


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _naive_clause(be: BreakEven) -> str:
    if be.kind == "crossover":
        return f"Ignoring quality, inventory and risk would have put the break-even at {be.volume:,.0f} units."
    return "Ignoring quality, inventory and risk would have shown no break-even."


def _decision(volume: float, preferred: str | None, advantage: float, pct: float | None,
              be: BreakEven, naive_be: BreakEven) -> str:
    if preferred is None:
        head = f"At {volume:,.0f} units per year the two options cost the same."
    else:
        pct_txt = f" ({pct * 100:.1f}%)" if pct is not None else ""
        head = f"At {volume:,.0f} units per year, {preferred} is cheaper by {_money(advantage)} per year{pct_txt}."
    if be.kind == "crossover":
        body = (f" The break-even volume is {be.volume:,.0f} units: {be.cheaper_above} is cheaper above it "
                f"and {be.cheaper_below} below it.")
    elif be.kind == "identical":
        body = " The two cost curves are identical, so there is no break-even."
    else:
        body = f" {be.cheaper_everywhere} is cheaper at every volume, so there is no break-even."
    return head + body + " " + _naive_clause(naive_be)


def compare(a: Option, b: Option, volume: float, horizon_years: int = 5,
            discount_rate: float = 0.10) -> MakeVsBuyResult:
    if volume < 0:
        raise ValueError("volume must be >= 0")
    if not isinstance(horizon_years, int) or not 1 <= horizon_years <= 10:
        raise ValueError("horizon_years must be an integer from 1 to 10")
    if discount_rate < 0:
        raise ValueError("discount_rate must be >= 0")
    if a.name == b.name:
        raise ValueError("the two options need different names")

    fa, va = effective_fixed(a, discount_rate, horizon_years), effective_variable(a)
    fb, vb = effective_fixed(b, discount_rate, horizon_years), effective_variable(b)
    ra, rb = _result(a, fa, va, volume), _result(b, fb, vb, volume)
    preferred = _preferred(ra, rb)
    costlier = max(ra.total_cost, rb.total_cost)
    advantage = abs(ra.total_cost - rb.total_cost)
    pct = advantage / costlier if costlier else None
    be = _break_even(fa, va, fb, vb, a.name, b.name)

    na = _result(a, a.fixed_annual, a.variable_per_unit, volume)
    nb = _result(b, b.fixed_annual, b.variable_per_unit, volume)
    naive_be = _break_even(a.fixed_annual, a.variable_per_unit, b.fixed_annual, b.variable_per_unit,
                           a.name, b.name)

    table = [
        {"factor": f, "volume": volume * f,
         "cost_a": fa + va * volume * f, "cost_b": fb + vb * volume * f}
        for f in VOLUME_FACTORS
    ]

    grid = []
    for bd in SENSITIVITY_DELTAS:  # rows: Buy (option B) variable-cost change
        row = []
        for md in SENSITIVITY_DELTAS:  # columns: Make (option A) variable-cost change
            a2 = replace(a, variable_per_unit=a.variable_per_unit * (1 + md))
            b2 = replace(b, variable_per_unit=b.variable_per_unit * (1 + bd))
            be2 = _break_even(fa, effective_variable(a2), fb, effective_variable(b2), a.name, b.name)
            row.append(be2.volume if be2.kind == "crossover" else None)
        grid.append(row)

    return MakeVsBuyResult(
        volume=volume,
        options=(ra, rb),
        preferred=preferred,
        advantage=advantage,
        advantage_pct=pct,
        break_even=be,
        naive_options=(na, nb),
        naive_preferred=_preferred(na, nb),
        naive_break_even=naive_be,
        volume_table=table,
        sensitivity={"buy_delta": list(SENSITIVITY_DELTAS), "make_delta": list(SENSITIVITY_DELTAS),
                     "break_even": grid},
        decision=_decision(volume, preferred, advantage, pct, be, naive_be),
    )


def compare_from_dict(payload: dict) -> dict:
    """JSON-friendly entry point used by the browser page.

    payload = {"volume": float, "horizon_years": int, "discount_rate": float,
               "a": {Option fields}, "b": {Option fields}}
    """
    from dataclasses import asdict

    result = compare(Option(**payload["a"]), Option(**payload["b"]), payload["volume"],
                     payload.get("horizon_years", 5), payload.get("discount_rate", 0.10))
    return asdict(result)
