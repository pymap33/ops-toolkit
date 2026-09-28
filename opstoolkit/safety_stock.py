"""Safety-stock and service-level cost optimizer -- tool 2.3.
Spec: docs/specs/03-safety-stock.md.

Continuous-review (Q, R) policy with normally distributed demand over a
constant lead time. Sizes EOQ, safety stock and reorder point; prices each
service level; and, given a cost per unit short, finds the cost-minimizing
service level.

Sources: eCampusOntario, "Fundamentals of Operations Management", section 8.5
(EOQ) and section 8.7 (safety stock, SS = Z * sigma_L, ROP = mean lead-time
demand + SS). The optimal-service-level result (critical ratio) is an extension
beyond that source, validated in tests by brute-force search.

Rates are decimals: 0.95 means 95%. Only the standard library is used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

_N = NormalDist()

# Service levels shown in the cost table (spec section 4).
TABLE_CSLS = (0.80, 0.85, 0.90, 0.95, 0.975, 0.99, 0.995, 0.999)


def normal_loss(z: float) -> float:
    """Standard normal loss function G(z) = E[max(X - z, 0)] = phi(z) - z * (1 - Phi(z))."""
    return _N.pdf(z) - z * (1 - _N.cdf(z))


def eoq(annual_demand: float, order_cost: float, holding_cost: float) -> float:
    return math.sqrt(2 * annual_demand * order_cost / holding_cost)


def order_cycle_cost(annual_demand: float, order_cost: float, holding_cost: float, q: float) -> float:
    """TC(Q) = S * D / Q + H * Q / 2 (ordering + cycle-stock holding)."""
    return order_cost * annual_demand / q + holding_cost * q / 2


@dataclass(frozen=True)
class Inputs:
    mean_demand: float  # units per period
    demand_std: float  # units per period
    lead_time: float  # periods, same unit as demand
    order_cost: float  # $ per order
    holding_cost: float  # $ per unit per year
    periods_per_year: float = 52.0
    order_quantity: float | None = None  # None = use EOQ
    target_csl: float = 0.95
    shortage_cost: float | None = None  # $ per unit short; None = no stockout-cost analysis

    def __post_init__(self) -> None:
        if self.mean_demand <= 0:
            raise ValueError("mean_demand must be > 0")
        if self.demand_std < 0:
            raise ValueError("demand_std must be >= 0")
        if self.lead_time <= 0:
            raise ValueError("lead_time must be > 0")
        if self.periods_per_year <= 0:
            raise ValueError("periods_per_year must be > 0")
        if self.order_cost < 0:
            raise ValueError("order_cost must be >= 0")
        if self.holding_cost <= 0:
            raise ValueError("holding_cost must be > 0")
        if self.order_quantity is None:
            if self.order_cost <= 0:
                raise ValueError("order_cost must be > 0 when the order quantity is left blank (EOQ needs it)")
        elif self.order_quantity <= 0:
            raise ValueError("order_quantity must be > 0")
        if not 0.5 <= self.target_csl <= 0.9999:
            raise ValueError("target_csl must be between 50% and 99.99%")
        if self.shortage_cost is not None and self.shortage_cost < 0:
            raise ValueError("shortage_cost must be >= 0")


@dataclass(frozen=True)
class ServicePoint:
    csl: float
    z: float
    safety_stock: float
    carrying_cost: float
    step_cost: float | None  # added carrying cost vs. the previous table row
    expected_short_per_cycle: float
    fill_rate: float
    stockout_cost: float | None
    total_cost: float | None  # carrying + stockout


@dataclass(frozen=True)
class Optimum:
    csl: float
    z: float
    safety_stock: float
    carrying_cost: float
    stockout_cost: float
    safety_plus_stockout: float
    target_safety_plus_stockout: float
    saving_vs_target: float
    critical_ratio: float
    clamped_at_zero: bool


@dataclass(frozen=True)
class SafetyStockResult:
    annual_demand: float
    lead_time_demand_mean: float
    lead_time_demand_std: float
    order_quantity: float
    used_eoq: bool
    orders_per_year: float
    ordering_cost: float
    cycle_holding_cost: float
    target: ServicePoint
    reorder_point: float
    total_inventory_cost: float  # ordering + cycle holding + safety carrying (+ stockout)
    table: list[ServicePoint]
    optimum: Optimum | None
    decision: str


def _point(csl: float, sigma_l: float, h: float, q: float, d: float,
           p: float | None, prev_carry: float | None) -> ServicePoint:
    z = _N.inv_cdf(csl)
    ss = z * sigma_l
    carry = ss * h
    short = sigma_l * normal_loss(z)
    stockout = (d / q) * p * short if p is not None else None
    return ServicePoint(
        csl=csl, z=z, safety_stock=ss, carrying_cost=carry,
        step_cost=None if prev_carry is None else carry - prev_carry,
        expected_short_per_cycle=short, fill_rate=1 - short / q,
        stockout_cost=stockout, total_cost=None if stockout is None else carry + stockout,
    )


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _decision(t: ServicePoint, rop: float, opt: Optimum | None) -> str:
    base = (f"At a {t.csl * 100:.1f}% cycle service level, hold {t.safety_stock:,.1f} units of safety stock "
            f"(reorder point {rop:,.1f} units); carrying it costs {_money(t.carrying_cost)} per year and gives a "
            f"fill rate of {t.fill_rate * 100:.2f}%.")
    if opt is None:
        return base + " Add a cost per unit short to find the service level that minimizes total cost."
    if opt.clamped_at_zero:
        return (base + " At this shortage cost, safety stock does not pay for itself: the cost-minimizing "
                "policy holds none (50% cycle service level).")
    return (base + f" The cost-minimizing service level is {opt.csl * 100:.2f}% (safety stock "
            f"{opt.safety_stock:,.1f} units), which lowers safety-stock plus shortage cost from "
            f"{_money(opt.target_safety_plus_stockout)} to {_money(opt.safety_plus_stockout)}, "
            f"a saving of {_money(opt.saving_vs_target)} per year.")


def compute(i: Inputs) -> SafetyStockResult:
    d = i.mean_demand * i.periods_per_year
    mu_l = i.mean_demand * i.lead_time
    sigma_l = i.demand_std * math.sqrt(i.lead_time)
    used_eoq = i.order_quantity is None
    q = eoq(d, i.order_cost, i.holding_cost) if used_eoq else i.order_quantity
    ordering = i.order_cost * d / q
    cycle_holding = i.holding_cost * q / 2
    p = i.shortage_cost

    target = _point(i.target_csl, sigma_l, i.holding_cost, q, d, p, None)
    rop = mu_l + target.safety_stock

    table = []
    prev = None
    for csl in TABLE_CSLS:
        pt = _point(csl, sigma_l, i.holding_cost, q, d, p, prev)
        table.append(pt)
        prev = pt.carrying_cost

    optimum = None
    if p is not None:
        ratio = math.inf if p == 0 else q * i.holding_cost / (p * d)
        critical = 1 - ratio
        clamped = critical <= 0.5
        csl_star = 0.5 if clamped else critical
        z_star = _N.inv_cdf(csl_star)
        opt_pt = _point(csl_star, sigma_l, i.holding_cost, q, d, p, None)
        opt_sum = opt_pt.carrying_cost + opt_pt.stockout_cost
        tgt_sum = target.carrying_cost + target.stockout_cost
        optimum = Optimum(
            csl=csl_star, z=z_star, safety_stock=opt_pt.safety_stock,
            carrying_cost=opt_pt.carrying_cost, stockout_cost=opt_pt.stockout_cost,
            safety_plus_stockout=opt_sum, target_safety_plus_stockout=tgt_sum,
            saving_vs_target=tgt_sum - opt_sum,
            critical_ratio=critical, clamped_at_zero=clamped,
        )

    total = ordering + cycle_holding + target.carrying_cost + (target.stockout_cost or 0.0)
    return SafetyStockResult(
        annual_demand=d, lead_time_demand_mean=mu_l, lead_time_demand_std=sigma_l,
        order_quantity=q, used_eoq=used_eoq, orders_per_year=d / q,
        ordering_cost=ordering, cycle_holding_cost=cycle_holding,
        target=target, reorder_point=rop, total_inventory_cost=total,
        table=table, optimum=optimum, decision=_decision(target, rop, optimum),
    )


def compute_from_dict(payload: dict) -> dict:
    """JSON-friendly entry point used by the browser page."""
    from dataclasses import asdict

    return asdict(compute(Inputs(**payload)))
