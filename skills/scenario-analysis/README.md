# Scenario analysis

Compare named operating cases and one-factor sensitivities against a preserved base. This portable financial workflow has a standalone case registry, strict override validation and exact operating cash calculations. Its outputs show the effective assumption changes, cash bridges, deltas and defined DSCR coverage.

Read [SKILL.md](SKILL.md), the [model contract](references/model-contract.md) and the [synthetic example](examples/README.md). Requires Python 3.11+ and no third-party dependencies.

## Run the example

From this package directory, choose a new output directory next to the package.

```sh
python scripts/scenario_analysis.py examples/cases.json --out ../scenario-analysis-run
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Read the results

Compare each case with the base assumptions and follow volume, price and costs through to cash available for debt service. The JSON retains exact fractions. The Markdown and CSV reports round displayed totals and identify periods with zero debt service. A case that leaves assumptions unchanged is flagged explicitly.

An optional [connected demonstration](examples/README.md#executed-debt-handoff) executes both engines using explicit script/input paths, checks a one-to-one period mapping and records evidence hashes. Its sibling debt package dependency is declared; the core scenario engine remains standalone.

## Scope

The user supplies taxes, capital expenditure, working capital and debt service. The core engine runs independently of the debt package. Forecast validation, scenario probabilities, covenant thresholds and Excel recalculation require separate review. Copyright and use terms are in [LICENSE](LICENSE).
