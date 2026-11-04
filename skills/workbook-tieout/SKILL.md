---
name: workbook-tieout
description: Reconcile explicitly mapped cells between two Excel workbooks, with declared periods, units and conversions. Use when checking re-keyed historical data, an actuals update, or a model against its identified source. Reports mismatches and incomplete coverage without changing either workbook.
compatibility: Python 3.11+ and openpyxl 3.1.5; XLSX files only.
---

# Workbook tieout

Establish whether the requested cells agree with an identified reference. Agreement is evidence of consistency; it does not establish that either workbook is accurate.

## Prepare the comparison

1. Identify the model, reference workbook, periods and unit/sign conventions. Read the relevant headers and source evidence. Do not infer currency or scale from a number's size.
2. Write an explicit mapping using the format in [the example guide](examples/README.md). Record a unique ID, sheet and cell on each side, the declared period and source unit, and the unit used for comparison. Different source units require a written conversion multiplier. A negative multiplier may encode a deliberate sign conversion; explain that decision in the review.
3. Confirm the requested coverage. The helper compares only listed pairs. It cannot discover omitted rows, verify the stated headers, or decide whether the source is authoritative. Include each material item; explain exclusions.
4. Set tolerances only for a justified precision rule. Defaults are exact. The allowed numeric difference is the greater of absolute tolerance and relative tolerance times the magnitude of the right-hand value. Tolerances are not widened automatically.

## Run and review

From this skill's directory:

```sh
python scripts/tieout.py model.xlsx source.xlsx --mapping mapping.json --out report.json
```

The helper opens inputs read-only and checks their hashes before and after. The report destination must be new. Blank cells, absent sheets, spreadsheet errors, invalid mappings and missing formula caches prevent a complete result. Text and booleans compare exactly by type; `true`, `1` and `"1"` are distinct.

| Exit | Status | Meaning |
|---|---|---|
| 0 | PASS | Every requested pair was compared using literal values and matched. |
| 1 | FAIL | Every pair was compared, and at least one differed. |
| 2 | INCOMPLETE | Mapping/input error or at least one uncomparable pair. Inspect any other mismatches in the report too. |
| 3 | REVIEW | All pairs matched, but at least one value came from an unverified saved formula cache. |

**Formula calculation is separate.** openpyxl does not calculate formulas. By default, mapped formulas produce INCOMPLETE. `--allow-cached-values` permits inspection of saved results; it does not prove freshness and can never turn an all-matching cached comparison into PASS. Arrange recalculation in a suitable spreadsheet engine separately, record its evidence, and state the limits of this helper. An absent cache remains INCOMPLETE even with the flag.

On a discrepancy, report both locations, original values, conversions, delta and tolerance. Investigate the evidence before changing either workbook. Do not choose a winner merely because it was called the source. Re-run after an authorized correction on stable files.

## Deliver

State the two filenames, requested/compared/matched/mismatched/incomplete counts, calculation status, material exclusions and report path. Zero comparisons never establishes a successful tieout. Never summarize a mapped subset as an audit of the entire workbook.

## Examples and tests

See [examples/README.md](examples/README.md) for a synthetic two-workbook exercise with a deliberate error. Run:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

The tests cover conversions, type differences, missing values, error cells, invalid mappings, tolerance boundaries and the distinction between formula caches and literal values.
