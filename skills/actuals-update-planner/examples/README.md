# Plan an annual update and derive a second quarter

The generator creates every workbook, number, source page and audit-status statement from scratch. No real company, financial disclosure or auditor is represented.

## Generate the plans

Run from the package directory with a new destination for each command.

```sh
python examples/make_demo.py --out /tmp/actuals-planner-demo --case annual
python scripts/plan.py /tmp/actuals-planner-demo/model.xlsx --mapping /tmp/actuals-planner-demo/mapping.json --sources /tmp/actuals-planner-demo/sources --out /tmp/actuals-planner-review
python examples/make_demo.py --out /tmp/actuals-planner-quarter-demo --case cumulative
python scripts/plan.py /tmp/actuals-planner-quarter-demo/model.xlsx --mapping /tmp/actuals-planner-quarter-demo/mapping.json --sources /tmp/actuals-planner-quarter-demo/sources --out /tmp/actuals-planner-quarter-review
```

Every destination must be new. Both plans exit 0 with `PLAN_READY`; the model remains byte-for-byte unchanged. The plan is a review artifact, not evidence that an update was applied.

## Compare the proposed entries

The annual case converts a source in USD thousands to a model in USD millions. The plan proposes revenue of 1,280 against an estimate of 1,200, signed costs of −720 against −700, and operating cash flow of 185 against 170. The gross-profit formulas and future assumptions are protected.

The quarter case derives Q2 from H1 minus Q1. Revenue is `675 − 300 = 375`; signed costs are `−410 − (−185) = −225`; operating cash flow is `120 − 50 = 70`. These calculations use source evidence, explicit quarter dates and prior model hardcodes. Future-quarter values are not computed by the helper.

Readable saved outputs: [annual-plan.md](annual-plan.md) and [cumulative-plan.md](cumulative-plan.md). Their machine-readable snapshots are [annual-plan.json](annual-plan.json) and [cumulative-plan.json](cumulative-plan.json); a fresh run calls that file `plan.json`. They include every source-sheet cell, typed value/formula, estimate snapshot, conversion, prior deduction, source hash and protected formula.

## Trace the annual figures

The [financial statement analysis case](https://github.com/noahsilv/skills/blob/main/skills/financial-statement-analysis/examples/README.md) uses the same synthetic disclosure for Cedar Circuit Components, consolidated FY2025. Both cases convert USD thousands to USD millions. Revenue and operating cash flow transfer directly. Cost of sales is a positive deduction in the normalized statements and a negative amount in the forecast model. Compare the disclosure's SHA-256 in the two JSON reports to confirm the source. The planner records the workbook and mapping hashes separately. Regenerated workbooks can have different hashes because XLSX metadata includes creation information.

The tests cover both commands and check source evidence, page references, changed files, period gaps, units and labels. They also check protected formulas, zero or negative estimates, duplicate entries, unmapped inputs and output preservation. The results apply to the calculator and its synthetic inputs.
