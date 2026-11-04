# Actuals update planner

Prepare a plan for updating a forecast model with reported financial results. The plan shows period derivations, scale and sign conversions, estimate snapshots and variances linked to sources. It uses strict schemas, explicit coverage, decimal arithmetic and source hashes, and protects formulas.

Read [SKILL.md](SKILL.md), [the mapping contract](references/schema.md) and [the synthetic examples](examples/README.md).

```sh
python -m pip install -r requirements.txt
python examples/make_demo.py --out /tmp/actuals-planner-demo --case annual
python scripts/plan.py /tmp/actuals-planner-demo/model.xlsx --mapping /tmp/actuals-planner-demo/mapping.json --sources /tmp/actuals-planner-demo/sources --out /tmp/actuals-planner-review
python -m unittest discover -s tests -p 'test_*.py' -v
```

Use new destinations. Requires Python 3.11+ and `openpyxl==3.1.5`. The helper reads XLSX without saving it. Source text may come from audited, unaudited or interim statements, with explicit evidence and status. Excerpt checks do not authenticate documents, confirm an audit opinion or prove original PDF transcription. The plan is limited to explicitly mapped monetary hardcodes; formula propagation and forecast effects remain uncalculated.

This is a local portfolio draft with no measured business-impact claim. The all-rights-reserved notice is in [LICENSE](LICENSE).
