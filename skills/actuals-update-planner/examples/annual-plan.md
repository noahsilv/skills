# Actuals update plan

Status: **PLAN_READY — review required before application**.

No workbook was changed or recalculated. The amounts below were computed from the declared inputs using decimal arithmetic; forecast and calculated-row effects are unknown.
Cedar Circuit Components (synthetic); consolidated; 2025-01-01 to 2025-12-31; USD scale 1000000.
Text excerpts and hashes verified. Source authenticity, audit opinion and original PDF-to-text transcription are not authenticated.

## Proposed model edits

| Sheet / cell | Before | Proposed value / formula |
|---|---|---|
| Forecast!C5 | 1200 | =&#x27;FY2025 Sources&#x27;!F3 |
| Forecast!C6 | -700 | =&#x27;FY2025 Sources&#x27;!F4 |
| Forecast!C9 | 170 | =&#x27;FY2025 Sources&#x27;!F5 |
| Forecast!C4 | FY2025E | FY2025A |

Create source sheet `FY2025 Sources` only after review. The complete typed cell instructions, including estimate snapshots and citations, are in plan.json/proposed_source_cells.

## Input variances

Percent = (actual − estimate) / abs(estimate) × 100; a zero estimate gives an undefined percentage. Positive does not imply favorable.

| Line | Estimate | Actual | Delta | Variance % | Evidence |
|---|---:|---:|---:|---:|---|
| Revenue | 1200 | 1280.000 | 80.000 | 6.666667 | synthetic-disclosure.txt p. 2: Revenue 1,280,000 |
| Cost of sales | -700 | -720.000 | -20.000 | -2.857143 | synthetic-disclosure.txt p. 2: Cost of sales (720,000) |
| Operating cash flow | 170 | 185.000 | 15.000 | 8.823529 | synthetic-disclosure.txt p. 2: Operating cash flow 185,000 |

## Protection and coverage

All existing cells except the enumerated proposed model edits remain protected; every existing formula remains protected.
Mapped inputs: 3. Target numeric hardcodes: 4. Protected existing formulas: 10.
Declared forecast columns: D (FY2026E), E (FY2027E).

Excluded rows:

- Row 8, Growth assumption: Forward driver assumption; not a reported financial result.

Declared source status:

- disclosure: audited; synthetic-disclosure.txt; SHA-256 410ab82040b573f1e95cd61af0e525a004a3cd62a1a0360fea9718fb2d960783.

Before applying: inspect the original audited report and the chosen source vintage, resolve exclusions, confirm period and sign conventions, and verify that current file hashes and cell contents still match this plan. Prior-period deductions use existing model hardcodes; their source accuracy requires separate review.
Apply only in an authorized copy using a suitable spreadsheet application. Recalculate there, verify the source links and changed period label, compare protected formulas/forecast inputs, and reconcile the completed workbook to the statements. This helper performs none of those application or post-change checks.
