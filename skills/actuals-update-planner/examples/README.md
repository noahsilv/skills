# Synthetic annual and quarter cases

The generator creates every workbook, number, source page and audit-status statement from scratch. No real company, financial disclosure or auditor is represented.

From the package directory:

```sh
python examples/make_demo.py --out /tmp/actuals-planner-demo --case annual
python scripts/plan.py /tmp/actuals-planner-demo/model.xlsx --mapping /tmp/actuals-planner-demo/mapping.json --sources /tmp/actuals-planner-demo/sources --out /tmp/actuals-planner-review
python examples/make_demo.py --out /tmp/actuals-planner-quarter-demo --case cumulative
python scripts/plan.py /tmp/actuals-planner-quarter-demo/model.xlsx --mapping /tmp/actuals-planner-quarter-demo/mapping.json --sources /tmp/actuals-planner-quarter-demo/sources --out /tmp/actuals-planner-quarter-review
```

Every destination must be new. Both plans exit 0 with `PLAN_READY`; the model remains byte-for-byte unchanged. The plan is a review artifact, not evidence that an update was applied.

The annual case converts a source in USD thousands to a model in USD millions. Revenue of 1,280 replaces a 1,200 estimate; signed costs of −720 replace −700; operating cash flow of 185 replaces 170. Gross-profit formulas and future assumptions remain protected.

The quarter case derives Q2 from H1 minus Q1. Revenue is `675 − 300 = 375`; signed costs are `−410 − (−185) = −225`; operating cash flow is `120 − 50 = 70`. These calculations use source evidence, explicit quarter dates and prior model hardcodes. Future-quarter values are not computed by the helper.

Readable saved outputs: [annual-plan.md](annual-plan.md) and [cumulative-plan.md](cumulative-plan.md). Their machine-readable snapshots are [annual-plan.json](annual-plan.json) and [cumulative-plan.json](cumulative-plan.json); a fresh run calls that file `plan.json`. They include every source-sheet cell, typed value/formula, estimate snapshot, conversion, prior deduction, source hash and protected formula.

The annual source text is shared with the [financial statement analysis case](../../financial-statement-analysis/examples/README.md). Both refer to Cedar Circuit Components (synthetic), consolidated FY2025, and USD millions normalized from USD thousands. Revenue and operating cash flow transfer directly; cost of sales is a positive deduction in normalized statements and a negative amount in the forecast model. The shared text SHA-256 in both JSON reports links the exact source snapshot, while the planner separately records the workbook and mapping hashes. Regenerated workbooks may have different binary hashes because XLSX metadata includes creation information; each plan records the workbook actually read.

The test suite exercises evidence failures, wrong physical pages, source/workbook changes, period gaps, incorrect units, source-label/number mismatches, formula protection, zero/negative estimate math, duplicate IDs/keys/rows, unmapped hardcodes, output preservation and the two documented CLI cases. It evaluates deterministic code on synthetic fixtures; no agent-vs-baseline or production-impact result is claimed.
