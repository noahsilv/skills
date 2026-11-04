# Model audit demonstration

Result: **FINDINGS**

Model: synthetic-debt-review. Amounts: USD millions.
Periods: 3. Checks: 21.
Recomputed covenant breach periods: Y3.
Final-principal target checked: True.
Absolute tolerances: money 0.000001; ratio 0.000001.

| Period | Check | Expected | Observed | Result |
| --- | --- | --- | --- | --- |
| Y1 | opening_debt | 100 | 100 | PASS |
| Y1 | closing_debt | 70 | 75 | FAIL |
| Y1 | principal_nonnegative | >= 0 | 70 | PASS |
| Y1 | debt_service | 40 | 50 | FAIL |
| Y1 | dscr | 5/4 | 1 | FAIL |
| Y1 | covenant | PASS | PASS | PASS |
| Y2 | opening_debt | 70 | 75 | FAIL |
| Y2 | closing_debt | 40 | 40 | PASS |
| Y2 | principal_nonnegative | >= 0 | 40 | PASS |
| Y2 | debt_service | 37 | 37 | PASS |
| Y2 | dscr | 6/5 | 6/5 | PASS |
| Y2 | covenant | PASS | PASS | PASS |
| Y2 | reported_continuity | 75 | 75 | PASS |
| Y3 | opening_debt | 40 | 40 | PASS |
| Y3 | closing_debt | 0 | 0 | PASS |
| Y3 | principal_nonnegative | >= 0 | 0 | PASS |
| Y3 | debt_service | 44 | 44 | PASS |
| Y3 | dscr | 1 | 1 | PASS |
| Y3 | covenant | FAIL | PASS | FAIL |
| Y3 | reported_continuity | 40 | 40 | PASS |
| Y3 | final_principal | 0 | 0 | PASS |

## Scope

- Normalized snapshot only; mapping and model-file identity are caller-supplied.
- No spreadsheet calculation, formula inspection, interest accrual verification or source-document review.
- Arithmetic is recomputed separately from reported outputs; this is not an independent professional audit.
- CHECKS_PASSED means checked outputs agree, not that covenants are met or a loan is affordable.

Snapshot SHA-256: `2477a87fd701e64a976b92d358957338df07097a12b5a8dd251dc12615932369`.
