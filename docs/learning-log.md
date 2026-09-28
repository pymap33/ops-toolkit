# Learning Log

One entry per tool: the one skill it was meant to teach, what was actually learned, and what surprised me.

| Date | Tool | Skill targeted | What I learned |
|---|---|---|---|
| 2026-09-28 | COPQ calculator | Turning quality data into a finance-grade savings case | Expected values computed in a standalone script *before* the library existed, so the tests could not just echo the implementation. Validation is definitional plus hand-computed until a published example is found. *(Draft note -- edit in your own words.)* |
| 2026-09-28 | Make-vs-Buy / TCO | Total-cost thinking: fixed + variable, annualizing one-time costs, and pricing hidden costs | Validated against a published textbook example read at the source, not a search summary. The summary's example was not on the cited page, so it went unused. Hidden costs (quality, inventory, risk) more than doubled the Make advantage and moved the break-even from 3,200 to 2,945 units. *(Draft note -- edit in your own words.)* |
| 2026-09-28 | Safety-Stock & Service-Level Optimizer | Turning a service-level target into a cost decision; demand statistics over lead time | Reading the textbook page directly exposed an error the search summary hid: the kiosk example prints ROP = 4 + 5 = 9 using the standard deviation where the mean lead-time demand (20) belongs, so the right answer is about 25. The optimal-service-level result is not in the book, so it was checked by brute-force search instead of citation. *(Draft note -- edit in your own words.)* |
