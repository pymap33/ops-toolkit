"""Cost of Poor Quality (COPQ) calculator -- tool 1.1. Spec: docs/specs/01-copq.md.

Classifies cost line items into the PAF categories (prevention, appraisal,
internal failure, external failure), totals the cost of quality, and prices an
optional improvement project: net annual savings, payback and NPV.

Framework source: ASQ, "What is Cost of Quality (COQ)?" --
CoQ = CoGQ (prevention + appraisal) + CoPQ (internal + external failure).

Rates (reduction, discount_rate) are decimals: 0.40 means 40%.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PREVENTION = "prevention"
APPRAISAL = "appraisal"
INTERNAL_FAILURE = "internal_failure"
EXTERNAL_FAILURE = "external_failure"
CATEGORIES = (PREVENTION, APPRAISAL, INTERNAL_FAILURE, EXTERNAL_FAILURE)

# Sensitivity grid axes (spec section 4): share of assumed reduction actually
# achieved, and one-time project cost relative to the estimate.
ACHIEVEMENT_FACTORS = (0.5, 0.75, 1.0)
COST_FACTORS = (0.75, 1.0, 1.25)


@dataclass(frozen=True)
class LineItem:
    """One cost line. Give either `annual_cost` (direct mode) or both `units`
    and `unit_cost` (driver mode), never a mix."""

    name: str
    category: str
    annual_cost: float | None = None
    units: float | None = None
    unit_cost: float | None = None
    reduction: float = 0.0  # fraction of this line's cost the project removes

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"{self.name!r}: category must be one of {CATEGORIES}, got {self.category!r}")
        direct = self.annual_cost is not None
        driver = self.units is not None or self.unit_cost is not None
        if direct == driver:
            raise ValueError(f"{self.name!r}: give either annual_cost or both units and unit_cost")
        if driver and (self.units is None or self.unit_cost is None):
            raise ValueError(f"{self.name!r}: driver mode needs both units and unit_cost")
        for label, value in (("annual_cost", self.annual_cost), ("units", self.units),
                             ("unit_cost", self.unit_cost)):
            if value is not None and value < 0:
                raise ValueError(f"{self.name!r}: {label} must be >= 0")
        if not 0.0 <= self.reduction <= 1.0:
            raise ValueError(f"{self.name!r}: reduction must be between 0 and 1")

    @property
    def cost(self) -> float:
        if self.annual_cost is not None:
            return float(self.annual_cost)
        return float(self.units) * float(self.unit_cost)


@dataclass(frozen=True)
class Project:
    one_time_cost: float
    added_annual_spend: float = 0.0
    horizon_years: int = 3
    discount_rate: float = 0.10

    def __post_init__(self) -> None:
        if self.one_time_cost < 0:
            raise ValueError("one_time_cost must be >= 0")
        if self.added_annual_spend < 0:
            raise ValueError("added_annual_spend must be >= 0")
        if not isinstance(self.horizon_years, int) or not 1 <= self.horizon_years <= 10:
            raise ValueError("horizon_years must be an integer from 1 to 10")
        if self.discount_rate < 0:
            raise ValueError("discount_rate must be >= 0")


@dataclass(frozen=True)
class ProjectResult:
    gross_savings: float
    net_annual_savings: float
    post_project_coq: float
    post_project_coq_pct_revenue: float | None
    payback_months: float | None  # None = never pays back
    npv: float
    savings_by_line: dict[str, float]
    sensitivity: dict  # {"achievement": [...], "cost": [...], "npv": [[...]]}
    decision: str


@dataclass(frozen=True)
class CopqResult:
    line_costs: dict[str, float]
    category_totals: dict[str, float]
    category_shares: dict[str, float]
    coq: float
    cogq: float
    copq: float
    coq_pct_revenue: float | None
    copq_pct_revenue: float | None
    project: ProjectResult | None = field(default=None)


def _npv(net_annual: float, one_time: float, rate: float, years: int) -> float:
    return sum(net_annual / (1 + rate) ** t for t in range(1, years + 1)) - one_time


def _payback_months(one_time: float, net_annual: float) -> float | None:
    if net_annual <= 0:
        return None
    return one_time / net_annual * 12


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _decision(net: float, payback: float | None, npv: float, project: Project) -> str:
    pay = "never pays back" if payback is None else f"pays back in {payback:.1f} months"
    return (
        f"At these assumptions the project saves {_money(net)} per year net, {pay} and has an NPV of "
        f"{_money(npv)} over {project.horizon_years} years at a {project.discount_rate * 100:.0f}% "
        "discount rate. Its result depends on the assumed reduction percentages: see the sensitivity table."
    )


def compute_copq(items: list[LineItem], revenue: float | None = None,
                 project: Project | None = None) -> CopqResult:
    if not items:
        raise ValueError("at least one line item is required")
    if revenue is not None and revenue < 0:
        raise ValueError("revenue must be >= 0")
    has_revenue = bool(revenue)  # blank or 0 -> percent-of-revenue outputs are n/a

    line_costs: dict[str, float] = {}
    for item in items:
        if item.name in line_costs:
            raise ValueError(f"duplicate line item name {item.name!r}")
        line_costs[item.name] = item.cost

    totals = {c: 0.0 for c in CATEGORIES}
    for item in items:
        totals[item.category] += item.cost
    coq = sum(totals.values())
    shares = {c: (totals[c] / coq if coq else 0.0) for c in CATEGORIES}
    cogq = totals[PREVENTION] + totals[APPRAISAL]
    copq = totals[INTERNAL_FAILURE] + totals[EXTERNAL_FAILURE]

    project_result = None
    if project is not None:
        savings_by_line = {i.name: i.cost * i.reduction for i in items}
        gross = sum(savings_by_line.values())
        net = gross - project.added_annual_spend
        post_coq = coq - gross + project.added_annual_spend
        payback = _payback_months(project.one_time_cost, net)
        npv = _npv(net, project.one_time_cost, project.discount_rate, project.horizon_years)
        grid = [
            [
                _npv(gross * a - project.added_annual_spend, project.one_time_cost * c,
                     project.discount_rate, project.horizon_years)
                for c in COST_FACTORS
            ]
            for a in ACHIEVEMENT_FACTORS
        ]
        project_result = ProjectResult(
            gross_savings=gross,
            net_annual_savings=net,
            post_project_coq=post_coq,
            post_project_coq_pct_revenue=post_coq / revenue if has_revenue else None,
            payback_months=payback,
            npv=npv,
            savings_by_line=savings_by_line,
            sensitivity={"achievement": list(ACHIEVEMENT_FACTORS), "cost": list(COST_FACTORS), "npv": grid},
            decision=_decision(net, payback, npv, project),
        )

    return CopqResult(
        line_costs=line_costs,
        category_totals=totals,
        category_shares=shares,
        coq=coq,
        cogq=cogq,
        copq=copq,
        coq_pct_revenue=coq / revenue if has_revenue else None,
        copq_pct_revenue=copq / revenue if has_revenue else None,
        project=project_result,
    )


def compute_from_dict(payload: dict) -> dict:
    """JSON-friendly entry point used by the browser page.

    payload = {"revenue": float|None,
               "items": [{"name", "category", "annual_cost"|("units","unit_cost"), "reduction"}],
               "project": {"one_time_cost", "added_annual_spend", "horizon_years", "discount_rate"} | None}
    Returns a plain dict (dataclasses expanded) so it serializes to JSON.
    """
    from dataclasses import asdict

    items = [LineItem(**row) for row in payload["items"]]
    project = Project(**payload["project"]) if payload.get("project") else None
    return asdict(compute_copq(items, payload.get("revenue"), project))
