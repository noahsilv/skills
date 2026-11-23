# Reconcile complete, incomplete and inconsistent statements

The three cases use invented entities, figures and source titles. The [synthetic disclosure](synthetic-disclosure.txt) also supplies the annual [actuals planner case](https://github.com/noahsilv/skills/blob/main/skills/actuals-update-planner/examples/README.md). The normalized input records the disclosure's SHA-256.

## Run the cases

Run each command from the package directory with a new output directory.

```sh
python scripts/analyze.py examples/complete.json --out /tmp/statement-analysis-review
python scripts/analyze.py examples/incomplete.json --out /tmp/statement-analysis-gap-review
python scripts/analyze.py examples/discrepancy.json --out /tmp/statement-analysis-difference-review
```

## Interpret the exit code

| Saved report | Exit code | Result |
| --- | ---: | --- |
| [Complete statements](complete-report/report.md) | 0 | The required inputs are present and the checks pass. |
| [Incomplete statements](incomplete-report/report.md) | 2 | The lease balance is explicitly missing and the foreign exchange cash movement is absent. |
| [Balance sheet discrepancy](discrepancy-report/report.md) | 1 | The balance sheet differs by one reporting unit. Reported other comprehensive income is zero. |

Each report has a JSON version alongside it with source references for every calculated result.

The tests distinguish missing values from zero and flag invalid references, incorrect units, duplicate periods and duplicate keys. They also cover reconciliation failures, tolerance boundaries, zero or negative denominators, decimal precision, changed source files and overwrite protection. The results apply to the calculator and its synthetic inputs.
