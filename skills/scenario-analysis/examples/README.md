# Synthetic operating cases

`cases.json` describes an invented operation with three annual periods. It combines units sold, unit prices, variable costs, fixed costs and explicitly supplied cash adjustments. The assumptions, cash payments and scenario choices are illustrative and carry no institutional thresholds or client evidence.

## Run the operating cases

Run from the package directory using a new output path.

```sh
python scripts/scenario_analysis.py examples/cases.json --out /tmp/scenario-analysis-example
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Interpret the stress results

Start with the [saved report](output/report.md). The [period results](output/period_results.csv) show the cash effects by period. The [JSON report](output/report.json) retains the exact values used in the calculations.

The cases cover the base, a 15 percent fall in volume, a 15 percent rise in fixed costs, both stresses together and higher first-period maintenance capital spending. Compare `combined` with `volume_down` to isolate the fixed-cost effect. Across the three periods, cash after debt service falls by 15 percent of total base fixed costs. Lower volume reduces both revenue and variable costs. Taxes, debt service and other cash adjustments stay at their specified values.

The first base period can be checked by hand: revenue is `10000 × 45 = 450000`; variable cost is `10000 × 18 = 180000`; EBITDA is `190000`. Deducting cash taxes `25000`, maintenance capex `20000` and working-capital increase `10000` gives CFADS `135000`. After debt service `80000`, cash is `55000` and DSCR is `1.6875`.

The one-factor outputs apply volume multipliers from 0.8 to 1.2 and price multipliers from 0.9 to 1.1. Identity multipliers reproduce the base exactly. These are separate experiments, not joint probability scenarios or a two-variable grid.

## Executed debt handoff

`connected-operating-case.json` is a second synthetic fixture with semiannual periods matching the optional sibling debt-schedule example. Its zero debt-service values are placeholders for the wrapper, not estimates to use for an economic conclusion. When both packages are present, run from this package directory:

```sh
python examples/run_connected_demo.py \
  --debt-script ../debt-schedule/scripts/debt_schedule.py \
  --debt-terms ../debt-schedule/examples/terms.json \
  --case-template examples/connected-operating-case.json \
  --out /tmp/connected-debt-scenario-example
```

The wrapper executes that explicit debt script, verifies currency, units, amount precision and identical date bounds, and maps each debt payment period to exactly one scenario period. It replaces only zero debt-service placeholders, refuses cases with debt-service overrides and runs the core scenario engine on the derived input. It records source/script/report hashes and every mapping in `handoff.json`, with a readable comparison in `handoff.md`. `connected-output/` contains the executed result.

The external debt package is required only for this optional demonstration. The normal scenario engine and all package unit tests run without it. An error may leave an incomplete new demonstration directory; use a fresh destination after correcting the inputs.
