# Review an annual actuals update

An analyst has replaced three estimates with reported results. Did the right amounts reach the model, and did a next-year assumption change during the update?

This harness runs the statement analysis, actuals planner, workbook tieout and model regression tools against one synthetic annual disclosure. It creates two model returns for comparison.

## Run

From the repository root, install the dependencies and run the harness.

```sh
python -m pip install -r requirements-dev.txt
python harnesses/actuals-review/run.py
```

To keep the workbooks and reports, supply a new output directory outside the checkout.

```sh
python harnesses/actuals-review/run.py --out ../actuals-review-run
```

## Read the result

| Model return | Source tieout | Model regression | Review finding |
| --- | --- | --- | --- |
| Reconciled | PASS | REVIEW | All three amounts agree with the disclosure. The three changes were declared. The growth assumption stays at 5 percent. |
| With exceptions | FAIL | FAIL | Signed cost of sales is USD18 million above the reported amount. Next year's growth assumption moves from 5 to 6 percent. |

Both returns change the cost cell, as expected. The regression check records its movement as declared in both. The source tieout catches the transposition from minus 720 to minus 702 million. A separate watch on the growth cell catches the one-percentage-point increase.

The harness exits successfully when it reproduces both outcomes. Inspect the [recorded summary](expected.json) for the individual checks.

## Follow the figures

1. The synthetic disclosure shows cost of sales as (720,000) in USD thousands. The statement analysis represents expenses as positive deductions.
2. The planner converts the amount to USD millions and preserves the model's negative expense sign. It proposes replacing the estimate of minus 700 million with minus 720 million.
3. The tieout compares the three submitted model cells with statement values on the same signed basis. The regression check compares the two model versions across four watched cells.

In a retained run, open `plan/plan.md` for the source citations and proposed edits. Open `exceptions/tieout.json` for the signed cost difference and `exceptions/regression.json` for the changed assumption. `summary.json` gives both verdicts.

## Scope

The fixtures use literal values for the reviewed cells. The harness verifies the disclosure hash and preserves the estimate workbook. Forecast formula outputs and the financial effect of the growth change require a separate recalculation.
