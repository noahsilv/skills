# Actuals update planner

Prepare a plan for updating a forecast model with reported financial results. The plan shows period derivations, scale and sign conversions, estimate snapshots and variances linked to sources. It uses strict schemas, explicit coverage, decimal arithmetic and source hashes, and protects formulas.

Read [SKILL.md](SKILL.md), [the mapping contract](references/schema.md) and [the synthetic examples](examples/README.md).

## Run the annual update

From this package directory, choose new sibling directories for the generated case and the review.

```sh
python -m pip install -r requirements.txt
python examples/make_demo.py --out ../actuals-planner-demo --case annual
python scripts/plan.py ../actuals-planner-demo/model.xlsx --mapping ../actuals-planner-demo/mapping.json --sources ../actuals-planner-demo/sources --out ../actuals-planner-review
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Review the plan

For each mapped monetary input, compare the estimate snapshot with the reported amount after the stated sign and unit conversions. The helper reads the workbook and writes a separate plan. Audited, unaudited and interim statements retain their supplied source labels. Document authenticity, original PDF transcription and the effects of changing a forecast formula require separate checks.

The example uses Python 3.11 or newer and `openpyxl==3.1.5`. Copyright and use terms are in [LICENSE](LICENSE).
