# Synthetic operating cases

`cases.json` describes an invented operation with three annual periods. It combines units sold, unit prices, variable costs, fixed costs and explicitly supplied cash adjustments. The assumptions, cash payments and scenario choices are illustrative and carry no institutional thresholds or client evidence.

From the package directory:

```sh
python scripts/scenario_analysis.py examples/cases.json --out /tmp/scenario-analysis-example
python -m unittest discover -s tests -p 'test_*.py' -v
```

Choose a new output path on each run. The checked-in `output/` directory is generated from this JSON and includes human-readable Markdown and CSVs plus exact JSON evidence.

The case registry covers base, a 15% volume reduction, 15% higher fixed costs, their combination and a first-period maintenance-capex increase. `combined` versus `volume_down` isolates the fixed-cost lever: total cash after debt service falls by 15% of the three base fixed-cost amounts. Volume stress reduces both revenue and variable costs. Taxes, debt service and the other cash adjustments stay at their explicit inputs in those cases.

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
