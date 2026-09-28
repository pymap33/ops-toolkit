# Validation

Every tool must reproduce at least one known answer from a cited source. Add one row per tool.

| Tool | Known-answer source | Test |
|---|---|---|
| COPQ calculator | Definitional identities (ASQ PAF framework: CoQ = CoGQ + CoPQ) and a hand-computed reference case (`docs/specs/01-copq.md` section 7), computed by a standalone script independent of the library. **No published numeric example found yet**: deep-research follow-up open. | `tests/test_copq.py` |
