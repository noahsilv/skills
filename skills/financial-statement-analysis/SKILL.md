---
name: financial-statement-analysis
description: Normalize historical financial statements into explicit entity, period, currency, scale and source records, then reconcile accounting identities and calculate defined metrics with coverage. Use for source-linked historical financial analysis, missing-data review or statement reconciliation. Produces JSON and a readable report from reviewed normalized inputs; excludes forecasts, valuations and credit ratings.
compatibility: Python 3.11+; standard library only; explicit normalized JSON input.
---

# Financial statement analysis

Build an analysis whose figures can be traced to the source and whose incomplete sections remain visible. This package implements a bounded historical analysis, with six accounting checks and eight metrics. It does not create a styled spreadsheet or independently extract or authenticate audited statements.

## Establish the data

1. Read the original statements and audit report. Confirm entity, consolidation scope, reporting basis, currency, scale, dates, and whether each source is audited, unaudited or interim. A source's audit status is a declaration in this input, not an assurance conclusion from the helper.
2. Select a comparative vintage explicitly. Where the latest statements restate an earlier period, use the selected restated figures consistently and identify the restatement in notes. Do not combine original and restated values silently. Resolve structural uncertainty about entity, dates or units before normalizing the affected period; continue other settled periods separately.
3. Normalize the reported lines using [the schema and definitions](references/schema.md). Retain the exact source document and page/table locator for each supplied value. Independently recheck material transcriptions against the original statement. The helper validates reference structure; it does not read those documents.
4. Use decimal strings, including `"0"` for a reported zero. Use `null` with an explanatory note for a known gap, or omit a field if it has not been reviewed. Never substitute zero for an absent amount or create a balancing plug.
5. Apply the declared sign convention. Cost of sales and operating expenses are positive deductions; cash flows and foreign-exchange cash movements are signed. Borrowings and lease fields are non-overlapping. Opening and closing cash must share the same cash-equivalent definition, and the equity rollforward must use net income and other comprehensive income for the same ownership scope.

## Run the analysis

From this package directory:

```sh
python scripts/analyze.py examples/complete.json --out /tmp/statement-analysis-review
```

Use a new destination for each run. The script reads one immutable input snapshot, checks for a changed input before delivery, and writes `report.json` and `report.md`. Decimal arithmetic retains reported precision; ratios alone are rounded to six decimal places. A reconciliation uses the explicitly declared absolute tolerance in the reporting units. Start at zero and justify any allowance by the source's rounding policy; the helper never chooses one.

| Exit | Result | Interpretation |
|---|---|---|
| 0 | COMPLETE | Every defined check agrees within the declared tolerance and every metric can be calculated. |
| 1 | DISCREPANCY | At least one evaluated accounting identity differs; other checks may also be unknown. |
| 2 | INCOMPLETE | Missing inputs or an undefined ratio prevent complete coverage. |
| 2 | ERROR, no report | The schema, types, source references or output destination are invalid. |

Review both reconciliation status and coverage. `UNKNOWN` is not agreement; a ratio with a zero or negative denominator is `UNDEFINED`. A reported zero numerator with a positive denominator remains a calculated zero. A COMPLETE result establishes only the implemented arithmetic consistency and coverage, not statement accuracy, financial strength, solvency, covenant compliance or audit assurance.

## Explain and deliver

Identify the entity and source vintage, date coverage and units. Report each discrepancy with the signed residual and the source-linked components. Distinguish absent fields from explicit missing values. Cite each metric's definition and source inputs rather than assigning universal traffic-light thresholds. Annual and interim flows remain as reported; the helper does not annualize or compare unlike periods.

Deliver the two reports, input hash, unresolved items and exclusions. Recheck transcription and classification errors against the original sources before changing inputs. Missing evidence remains an open item; a clean arithmetic result cannot resolve it.

## Examples and checks

Read [examples/README.md](examples/README.md) for complete, incomplete and discrepancy cases, and run:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

These are deterministic helper tests. They do not measure whether an agent consistently chooses the skill or correctly interprets new financial statements.
