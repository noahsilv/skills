---
name: scenario-analysis
description: Build a reproducible financial case registry, preserve the base assumptions, validate overrides and compare named cases with isolated one-factor sensitivities. Use for base/downside comparisons, operating cash stress tests or tracing which assumptions change a result. Includes a standalone volume-price-cost cash model with explicit debt service and exact arithmetic; does not recalculate Excel workbooks.
compatibility: Python 3.11+; standard library only.
---

# Scenario analysis

Make every case reproducible from a common, preserved base. Separate the registry of changes from the equations that turn assumptions into outputs. Review the effective changes and their financial meaning before presenting the resulting case comparison.

## Set up the analysis

1. Identify the decision, periods, currency, amount units and base assumptions. The bundled engine models revenue from volume × unit price, deducts variable and fixed operating costs, and bridges EBITDA to cash available for debt service (CFADS). Read [the model and input contract](references/model-contract.md) before choosing it.
2. Populate each period explicitly. Cash taxes, maintenance capex, working-capital increases and debt-service payments are supplied inputs. Negative working-capital increases represent releases. Other assumptions must remain nonnegative. The model has no automatic tax response, debt schedule or growth compounding.
3. Put `base` first with no overrides. Register each named case once with an explicit `replace`, `add` or `multiply` operation for each changed assumption. All operations apply directly to base. Explain the case's economic rationale in the accompanying analysis; a combined case is not inherently plausible because it runs successfully.
4. Add one-factor sensitivity axes for the levers being investigated. Each axis level changes one assumption across all periods, independently of other axes and named cases. Include an identity value where useful: multiplier 1 or additive change 0.

## Run and inspect

From this package's directory:

```sh
python scripts/scenario_analysis.py examples/cases.json --out /tmp/scenario-analysis-run
```

The output directory must be new. The helper validates input types, fields, IDs, dates, array lengths and effective assumptions, evaluates each case, and records the input hash. Source files and the base object remain unchanged. Exit 0 means the calculation completed; exit 2 identifies invalid input or I/O failure. A write failure can leave an incomplete newly created directory; rerun to a fresh destination after resolving it.

Read `report.md` for the comparison, `cases.csv` for totals and deltas, `period_results.csv` for the cash bridge, `assumption_changes.csv` for effective changes, and `sensitivities.csv` for the one-factor results. `report.json` includes exact rational results, applied assumptions, source hashes and full sensitivity period calculations. CSVs round only their display values; the model uses exact arithmetic throughout.

## Verify the causal story

1. Reconcile a base period independently: revenue minus variable and fixed operating costs gives EBITDA; subtract explicit cash taxes, maintenance capex and working-capital increase to obtain CFADS; deduct debt service to obtain cash after debt service.
2. Confirm `base_preserved` and inspect the base input hash. Every case starts from base, so running a downside before a cost case cannot carry the downside into the cost case.
3. Inspect every `NO_ASSUMPTION_CHANGE` and `ASSUMPTIONS_CHANGED_OUTPUT_UNCHANGED` status. An unchanged output can result from a redundant override or a financially inactive assumption; it is not automatically a wiring error. Compare exact results when display rounding hides a small change.
4. Isolate a lever using two cases that differ only in that lever. In the example, `combined` versus `volume_down` isolates the fixed-cost change. Base versus a combined case does not establish which lever caused which movement.
5. Review DSCR period coverage. A zero debt-service denominator produces an undefined ratio, not zero or infinity. The summary shows the minimum defined period DSCR and how many periods supplied a defined ratio. No covenant threshold or pass/fail covenant conclusion is assumed.

## Deliver and bound the result

State the base, case changes, period coverage, relevant results and source hash. Separate computed effects from the rationale for selecting assumptions. Include cash shortfalls without inserting a funding plug. Rerun after any input change; prior reports are snapshots tied to their hashes.

The optional [debt-schedule handoff](references/model-contract.md#debt-schedule-handoff) is a manual mapping with matching periods, currency and units. The engine has no cross-package runtime dependency. A debt-rate shock requires a separate debt calculation and updated debt-service inputs; adding an unknown `interest_rate` key is rejected.

The engine is a bounded operating cash model, not a three-statement forecast, valuation model, tax solver, loan documentation review, probabilistic simulation or spreadsheet calculation service.

## Examples and verification

See [the synthetic example](examples/README.md), then run:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

Tests cover independently calculated outputs, immutable base and case-order invariance, isolated levers, sensitivity identity, signed cash flows, undefined coverage ratios, exact rounding, strict validation and non-overwriting CLI outputs. They do not measure agent trigger selection or claim an external benchmark.
