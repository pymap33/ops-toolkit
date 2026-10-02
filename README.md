# Ops Toolkit

Cost-modeling and operations-finance calculators for the space where Lean/Six Sigma meets finance: pricing quality, capacity and uncertainty in dollars. Each tool runs both as a plain Python library and as a static browser page (via [Pyodide](https://pyodide.org/)) with no server and no data leaving the page.

> Educational tools, not professional advice. Uses synthetic or public data only.

## Tools

| Tool | Status |
|---|---|
| [Cost of Poor Quality (COPQ) calculator](web/calculator-copq.html) | Built; `opstoolkit/copq.py`, spec in `docs/specs/01-copq.md` |
| [Make-vs-Buy / TCO calculator](web/calculator-make-vs-buy.html) | Built; `opstoolkit/make_vs_buy.py`, spec in `docs/specs/02-make-vs-buy.md` |
| [Safety-Stock & Service-Level Cost Optimizer](web/calculator-safety-stock.html) | Built; `opstoolkit/safety_stock.py`, spec in `docs/specs/03-safety-stock.md` |
| [Sample-Size & Cost-of-Testing Planner](web/calculator-sample-size.html) | Built; `opstoolkit/sample_size.py`, spec in `docs/specs/04-sample-size.md` |
| [Process-Chain Should-Cost Builder](web/calculator-should-cost.html) | Built; `opstoolkit/should_cost.py`, spec in `docs/specs/05-flex-should-cost.md` |

A "Which tool do I need?" table will go here as tools ship.

## Layout

```
opstoolkit/   Core library (pure Python, no dependencies); manifest.json is generated
tests/        pytest suite, no network required
scripts/      generate_manifest.py -- run after adding/removing a module or data file
web/          Static Pyodide pages: index.html hub, one page per tool, shared/loader.js
data/         Static JSON inputs used by tools
docs/         decisions.md, learning-log.md, validation.md
templates/    tool-spec-template.md -- fill in before coding each tool
```

## Development

```
pip install -r requirements-dev.txt
python scripts/generate_manifest.py
python -m pytest
```

## License

MIT
