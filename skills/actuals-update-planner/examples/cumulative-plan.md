# Actuals update plan

Status: **PLAN_READY — review required before application**.

No workbook was changed or recalculated. The amounts below were computed from the declared inputs using decimal arithmetic; forecast and calculated-row effects are unknown.
Cedar Circuit Components (synthetic); consolidated; 2025-04-01 to 2025-06-30; USD scale 1000000.
Text excerpts and hashes verified. Source authenticity, audit opinion and original PDF-to-text transcription are not authenticated.

## Proposed model edits

| Sheet / cell | Before | Proposed value / formula |
|---|---|---|
| Forecast!C5 | 330 | =&#x27;Q2 2025 Sources&#x27;!F3 |
| Forecast!C6 | -200 | =&#x27;Q2 2025 Sources&#x27;!F4 |
| Forecast!C9 | 60 | =&#x27;Q2 2025 Sources&#x27;!F5 |
| Forecast!C4 | Q2 2025E | Q2 2025A |

Create source sheet `Q2 2025 Sources` only after review. The complete typed cell instructions, including estimate snapshots and citations, are in plan.json/proposed_source_cells.

## Input variances

Percent = (actual − estimate) / abs(estimate) × 100; a zero estimate gives an undefined percentage. Positive does not imply favorable.

| Line | Estimate | Actual | Delta | Variance % | Evidence |
|---|---:|---:|---:|---:|---|
| Revenue | 330 | 375.000 | 45.000 | 13.636364 | synthetic-disclosure.txt p. 2: Revenue 675,000 |
| Cost of sales | -200 | -225.000 | -25.000 | -12.500000 | synthetic-disclosure.txt p. 2: Cost of sales (410,000) |
| Operating cash flow | 60 | 70.000 | 10.000 | 16.666667 | synthetic-disclosure.txt p. 2: Operating cash flow 120,000 |

## Protection and coverage

All existing cells except the enumerated proposed model edits remain protected; every existing formula remains protected.
Mapped inputs: 3. Target numeric hardcodes: 4. Protected existing formulas: 10.
Declared forecast columns: D (Q3 2025E), E (Q4 2025E).

Excluded rows:

- Row 8, Growth assumption: Forward driver assumption; not a reported financial result.

Declared source status:

- disclosure: interim; synthetic-disclosure.txt; SHA-256 5a046ed815f6e5ae71fb4b1853129d9833f5e0277bcc0abb71c358c000baf2c3.

Before applying: inspect the original audited report and the chosen source vintage, resolve exclusions, confirm period and sign conventions, and verify that current file hashes and cell contents still match this plan. Prior-period deductions use existing model hardcodes; their source accuracy requires separate review.
Apply only in an authorized copy using a suitable spreadsheet application. Recalculate there, verify the source links and changed period label, compare protected formulas/forecast inputs, and reconcile the completed workbook to the statements. This helper performs none of those application or post-change checks.
