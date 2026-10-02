"""Process-chain should-cost builder -- tool 3.6 (rough estimation).
Spec: docs/specs/05-flex-should-cost.md.

Builds a price bottom-up for a web-based product made through an ordered chain of
process steps (extrusion, print, laminate, pouch-make, ...), each of which can be
flagged as a hand-off to a separate company (margin stacking). All prices and rates
are user inputs; the tool ships no market data. Results are a rough estimate with
a bounding range, not a confidence interval.

Structure sources: BN Pack, "How to Calculate Film Yield and Packaging Cost per
Unit" (lanes, repeat, roll yield, waste waterfall) and DFMA / Boothroyd Dewhurst,
"Plastic Extrusion Cost Estimating" (rate / speed, die amortization). See
docs/validation.md for the verification and the source error found.

Rates are decimals: 0.98 means 98%. Prices are $/kg. Only the standard library is used.
"""

from __future__ import annotations

from dataclasses import dataclass

LB_PER_KG = 2.2046226218
WATER_IN3_PER_LB = 27.68  # 1 lb of water = 27.68 cubic inches


def film_yield_in2_per_lb(thickness_mils: float, specific_gravity: float) -> float:
    """Square inches per pound of film: 27,680 / (mils x SG)."""
    return WATER_IN3_PER_LB * 1000.0 / (thickness_mils * specific_gravity)


@dataclass(frozen=True)
class Material:
    name: str
    price_per_kg: float
    step: str  # name of the step at which this material enters
    gsm: float | None = None  # g/m2
    thickness_um: float | None = None
    density: float | None = None  # g/cm3

    def __post_init__(self) -> None:
        if self.price_per_kg < 0:
            raise ValueError(f"material '{self.name}': price must be >= 0")
        if self.gsm is None:
            if self.thickness_um is None or self.density is None:
                raise ValueError(f"material '{self.name}': give gsm, or thickness and density")
            if self.thickness_um <= 0 or self.density <= 0:
                raise ValueError(f"material '{self.name}': thickness and density must be > 0")
        elif self.gsm <= 0:
            raise ValueError(f"material '{self.name}': gsm must be > 0")

    @property
    def weight_gsm(self) -> float:
        """g/m2; thickness (um) x density (g/cm3) is dimensionally g/m2."""
        return self.gsm if self.gsm is not None else self.thickness_um * self.density


@dataclass(frozen=True)
class Step:
    name: str
    rate_per_hr: float
    speed: float
    speed_unit: str = "m_per_min"  # or "kg_per_hr"
    setup_hr: float = 0.0
    setup_waste_m: float = 0.0
    run_yield: float = 1.0
    handoff: bool = False  # hand-off to a separate company after this step
    overhead: float | None = None  # per-step override
    margin: float | None = None  # per-step override

    def __post_init__(self) -> None:
        if self.rate_per_hr < 0:
            raise ValueError(f"step '{self.name}': rate must be >= 0")
        if self.speed <= 0:
            raise ValueError(f"step '{self.name}': speed must be > 0")
        if self.speed_unit not in ("m_per_min", "kg_per_hr"):
            raise ValueError(f"step '{self.name}': speed_unit must be 'm_per_min' or 'kg_per_hr'")
        if self.setup_hr < 0 or self.setup_waste_m < 0:
            raise ValueError(f"step '{self.name}': setup time and waste must be >= 0")
        if not 0 < self.run_yield <= 1:
            raise ValueError(f"step '{self.name}': run yield must be in (0, 100%]")
        if self.overhead is not None and self.overhead < 0:
            raise ValueError(f"step '{self.name}': overhead must be >= 0")
        if self.margin is not None and not 0 <= self.margin < 1:
            raise ValueError(f"step '{self.name}': margin must be in [0, 100%)")


@dataclass(frozen=True)
class Inputs:
    materials: list[Material]
    steps: list[Step]
    units: float  # good units required
    units_per_m: float  # good units per metre of web (lanes / repeat)
    web_width_m: float = 1.0
    tooling_cost: float = 0.0
    tooling_amort_qty: float = 1.0
    overhead: float = 0.12
    margin: float = 0.15
    band_price: float = 0.15  # +/- on prices and rates for the range
    band_speed: float = 0.15
    band_yield: float = 0.02  # +/- points
    quote_per_1000: float | None = None

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("at least one process step is needed")
        names = [s.name for s in self.steps]
        if len(set(names)) != len(names):
            raise ValueError("step names must be unique")
        for m in self.materials:
            if m.step not in names:
                raise ValueError(f"material '{m.name}' enters at unknown step '{m.step}'")
        if self.units <= 0:
            raise ValueError("units must be > 0")
        if self.units_per_m <= 0:
            raise ValueError("units per web metre must be > 0")
        if self.web_width_m <= 0:
            raise ValueError("web width must be > 0")
        if self.tooling_cost < 0 or self.tooling_amort_qty <= 0:
            raise ValueError("tooling cost must be >= 0 and its amortization quantity > 0")
        if self.overhead < 0:
            raise ValueError("overhead must be >= 0")
        if not 0 <= self.margin < 1:
            raise ValueError("margin must be in [0, 100%)")
        if min(self.band_price, self.band_speed, self.band_yield) < 0 or self.band_price >= 1 or self.band_speed >= 1:
            raise ValueError("uncertainty bands must be >= 0 (price and speed bands below 100%)")
        if self.quote_per_1000 is not None and self.quote_per_1000 <= 0:
            raise ValueError("quote must be > 0")


@dataclass(frozen=True)
class StageRow:
    step: str
    input_length_m: float
    material_cost: float
    conversion_cost: float
    base: float  # upstream transfer price + this step's material + conversion
    overhead: float
    margin: float
    tooling: float
    price_out: float  # transfer price after this step
    is_handoff: bool  # overhead and margin were taken at this step


@dataclass(frozen=True)
class Scenario:
    price: float
    stages: list[StageRow]
    material_total: float
    conversion_total: float
    overhead_total: float
    margin_total: float
    tooling_total: float
    material_by_layer: dict[str, float]


@dataclass(frozen=True)
class Sensitivity:
    label: str
    price_per_1000: float
    change_per_1000: float


@dataclass(frozen=True)
class ShouldCostResult:
    price: float
    price_per_1000: float
    cost: float  # price - margin
    material_total: float
    conversion_total: float
    waste_cost: float
    tooling_total: float
    overhead_total: float
    margin_total: float
    stages: list[StageRow]
    material_by_layer: dict[str, float]
    low_per_1000: float
    high_per_1000: float
    sensitivity: list[Sensitivity]
    quote_position: str | None
    quote_gap: float | None  # $ per 1,000, quote minus base
    quote_gap_pct: float | None
    implied_margin: float | None
    decision: str


def _scenario(i: Inputs, ps: float = 1.0, rs: float = 1.0, ss: float = 1.0, yield_shift: float = 0.0,
              perfect: bool = False, units_factor: float = 1.0) -> Scenario:
    """One pass through the chain. ps/rs/ss scale prices, rates and speeds; yield_shift moves run yields."""
    units = i.units * units_factor
    out_len = units / i.units_per_m
    n = len(i.steps)
    in_len = [0.0] * n
    for k in range(n - 1, -1, -1):  # backwards from the good output
        s = i.steps[k]
        y = 1.0 if perfect else min(1.0, max(1e-6, s.run_yield + yield_shift))
        sw = 0.0 if perfect else s.setup_waste_m
        in_len[k] = out_len / y + sw
        out_len = in_len[k]

    index = {s.name: k for k, s in enumerate(i.steps)}
    cum_gsm = []
    running = 0.0
    for k in range(n):
        running += sum(m.weight_gsm for m in i.materials if index[m.step] == k)
        cum_gsm.append(running)

    transfer = 0.0
    rows: list[StageRow] = []
    by_layer: dict[str, float] = {}
    for k, s in enumerate(i.steps):
        mat = 0.0
        for m in i.materials:
            if index[m.step] == k:
                c = in_len[k] * i.web_width_m * m.weight_gsm * m.price_per_kg * ps / 1000.0
                by_layer[m.name] = by_layer.get(m.name, 0.0) + c
                mat += c
        speed = s.speed * ss
        if s.speed_unit == "m_per_min":
            run_hr = in_len[k] / speed / 60.0
        else:
            run_hr = in_len[k] * i.web_width_m * cum_gsm[k] / 1000.0 / speed
        conv = (s.setup_hr + run_hr) * s.rate_per_hr * rs
        base = transfer + mat + conv
        last = k == n - 1
        if last or s.handoff:
            oh = s.overhead if s.overhead is not None else i.overhead
            mg = s.margin if s.margin is not None else i.margin
            tool = i.tooling_cost / i.tooling_amort_qty * units if last else 0.0
            cost = base * (1.0 + oh) + tool
            out = cost / (1.0 - mg)
            rows.append(StageRow(s.name, in_len[k], mat, conv, base, base * oh, out - cost, tool, out, True))
        else:
            out = base
            rows.append(StageRow(s.name, in_len[k], mat, conv, base, 0.0, 0.0, 0.0, out, False))
        transfer = out

    return Scenario(
        price=transfer, stages=rows,
        material_total=sum(r.material_cost for r in rows), conversion_total=sum(r.conversion_cost for r in rows),
        overhead_total=sum(r.overhead for r in rows), margin_total=sum(r.margin for r in rows),
        tooling_total=sum(r.tooling for r in rows), material_by_layer=by_layer,
    )


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _decision(i: Inputs, base_1000: float, low: float, high: float, handoffs: int, pos: str | None,
              gap: float | None, gap_pct: float | None) -> str:
    s = (f"Rough should-cost is {_money(base_1000)} per 1,000 (range {_money(low)} to {_money(high)}, an outer bound, "
         f"not a confidence interval)")
    s += f", with {handoffs} hand-off{'s' if handoffs != 1 else ''} to separate companies before the buyer." if handoffs else ", all steps in one company."
    if pos is None:
        return s
    where = {"below": "below the range", "inside": "inside the range", "above": "above the range"}[pos]
    return s + (f" The quote of {_money(i.quote_per_1000)} is {where}: {_money(abs(gap))} "
                f"({abs(gap_pct) * 100:.0f}%) {'over' if gap > 0 else 'under'} the base case.")


def compute(i: Inputs) -> ShouldCostResult:
    k = 1000.0 / i.units
    base = _scenario(i)
    perfect = _scenario(i, perfect=True)
    waste = (base.material_total + base.conversion_total) - (perfect.material_total + perfect.conversion_total)

    low = _scenario(i, 1 - i.band_price, 1 - i.band_price, 1 + i.band_speed, +i.band_yield).price * k
    high = _scenario(i, 1 + i.band_price, 1 + i.band_price, 1 - i.band_speed, -i.band_yield).price * k
    base_1000 = base.price * k

    sens = []
    for label, kwargs in [
        ("Material prices +10%", dict(ps=1.10)),
        ("Machine rates +10%", dict(rs=1.10)),
        ("Speeds -10%", dict(ss=0.90)),
        ("Run yields -2 points", dict(yield_shift=-0.02)),
        ("Order quantity halved", dict(units_factor=0.5)),
    ]:
        sc = _scenario(i, **kwargs)
        per = sc.price * 1000.0 / (i.units * kwargs.get("units_factor", 1.0))
        sens.append(Sensitivity(label, per, per - base_1000))

    pos = gap = gap_pct = implied = None
    if i.quote_per_1000 is not None:
        q = i.quote_per_1000
        pos = "below" if q < low else ("above" if q > high else "inside")
        gap = q - base_1000
        gap_pct = gap / base_1000
        implied = 1.0 - ((base.price - base.margin_total) * k) / q

    handoffs = sum(1 for r in base.stages[:-1] if r.is_handoff)
    return ShouldCostResult(
        price=base.price, price_per_1000=base_1000, cost=base.price - base.margin_total,
        material_total=base.material_total, conversion_total=base.conversion_total, waste_cost=waste,
        tooling_total=base.tooling_total, overhead_total=base.overhead_total, margin_total=base.margin_total,
        stages=base.stages, material_by_layer=base.material_by_layer,
        low_per_1000=low, high_per_1000=high, sensitivity=sens,
        quote_position=pos, quote_gap=gap, quote_gap_pct=gap_pct, implied_margin=implied,
        decision=_decision(i, base_1000, low, high, handoffs, pos, gap, gap_pct),
    )


def inputs_from_dict(p: dict) -> Inputs:
    """Build Inputs from the plain dict the browser page sends (nested lists of dicts)."""
    mats = [Material(**m) for m in p.pop("materials")]
    steps = [Step(**s) for s in p.pop("steps")]
    return Inputs(materials=mats, steps=steps, **p)


def compute_from_dict(payload: dict) -> dict:
    """JSON-friendly entry point used by the browser page."""
    from dataclasses import asdict

    return asdict(compute(inputs_from_dict(dict(payload))))
