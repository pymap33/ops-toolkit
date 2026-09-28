# Validation

Every tool must reproduce at least one known answer from a cited source. Add one row per tool.

| Tool | Known-answer source | Test |
|---|---|---|
| COPQ calculator | Definitional identities (ASQ PAF framework: CoQ = CoGQ + CoPQ) and a hand-computed reference case (`docs/specs/01-copq.md` section 7), computed by a standalone script independent of the library. **No published numeric example found yet**: deep-research follow-up open. | `tests/test_copq.py` |
| Make-vs-Buy / TCO calculator | **Published example, verified at the source 2026-09-28:** ABX Company, eCampusOntario *Fundamentals of Operations Management* §4.10 (break-even 3,200 units; $260,000 vs $150,000 at 1,000 units). Plus algebraic checks and a hand-computed TCO case (`docs/specs/02-make-vs-buy.md` §7) from a standalone script. | `tests/test_make_vs_buy.py` |
