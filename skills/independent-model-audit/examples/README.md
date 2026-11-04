# Synthetic model-audit cases

All figures and cell references are fictional. The model hash is the digest of a fixture identity string, not a workbook. No external financial data is included.

The three annual periods start with USD 100 million of principal. Repayments are 30, 30 and 40; supplied cash interest is 10, 7 and 4. Independently adding repayment and cash interest gives debt service of 40, 37 and 44. CFADS of 50, 44.4 and 44 gives DSCR of 1.25, 1.2 and 1.0. The explicitly chosen minimum ratio is 1.2. This is an example assumption, not a lending-policy threshold.

| Case | What changes | Expected result |
| --- | --- | --- |
| [Clean](clean.json) | Correct saved outputs, including the Y3 covenant breach. | `CHECKS_PASSED`: 21 comparisons pass; Y3 is listed as an economic breach. |
| [Planted errors](planted-errors.json) | Wrong Y1 closing carried into Y2 opening; wrong service and ratio in Y1; Y3 breach hidden. | `FINDINGS`: five failed comparisons. The wrong reported balance still passes reported continuity. |
| [Missing data](missing-data.json) | Y2 CFADS, reported ratio and covenant are unavailable. | `INCOMPLETE`: two checks are unverified; neither is counted as passed. |

Saved reports: [clean](clean-output/report.md), [planted errors](planted-errors-output/report.md), [missing data](missing-data-output/report.md).

From the package directory, choose fresh output paths:

```sh
python scripts/audit_model.py examples/clean.json --out /tmp/model-audit-clean
python scripts/audit_model.py examples/planted-errors.json --out /tmp/model-audit-errors
python scripts/audit_model.py examples/missing-data.json --out /tmp/model-audit-missing
```

The latter two commands return exit 1 with completed reports. A failing audit check is a demonstrated result, not a CLI failure. Exit 2 indicates invalid input or an I/O failure.

`make_examples.py` regenerates the three JSON inputs from declared fictional values. It overwrites those fixture files only. The audit CLI refuses to overwrite reports.

The cases demonstrate arithmetic checking of a mapped snapshot. They do not demonstrate workbook extraction, recalculation, interest accrual verification or an independent review team.
