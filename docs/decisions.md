# Design Decisions

Short log of choices that shape the toolkit, newest last. Each entry: what, why, alternative rejected.

## 2026-09-27 -- One repo, hub + per-tool pages
Every tool lives in this repo behind a hub page rather than in its own repo. Shared validation helpers, page shell and CI are written once, and the portfolio reads as one body of work. Rejected: one repo per tool (duplicated infrastructure, ten thin repos). Split by family later only if a tool outgrows this repo.

## 2026-09-27 -- Python core + Pyodide browser pages
Logic is a tested pure-Python library; each browser page is a thin layer that runs the same code via Pyodide, so tests cover what users run. Same pattern as wacc-toolkit. Rejected: reimplementing logic in JS (two copies drift).

## 2026-09-27 -- Manifest-generated fetch list, `.nojekyll`
Carried over from wacc-toolkit's live-site bugs: a hand-maintained module fetch list broke the browser page, and Jekyll silently 404s underscore-prefixed files such as `__init__.py`. The manifest is generated and guarded by `tests/test_manifest.py`.

## 2026-09-27 -- CI runs pytest on every push
Visible test status is part of the portfolio signal. Pages is branch-based, so no deploy workflow is needed.
