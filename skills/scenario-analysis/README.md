# Scenario analysis

Compare named operating cases and one-factor sensitivities against a preserved base. This portable financial workflow has a standalone case registry, strict override validation and exact operating cash calculations. Its outputs show the effective assumption changes, cash bridges, deltas and defined DSCR coverage.

Read [SKILL.md](SKILL.md), the [model contract](references/model-contract.md) and the [synthetic example](examples/README.md). Requires Python 3.11+ and no third-party dependencies.

```sh
python scripts/scenario_analysis.py examples/cases.json --out /tmp/scenario-analysis-run
python -m unittest discover -s tests -p 'test_*.py' -v
```

Use a new output directory. The input file and base assumptions remain unchanged. Exact rational arithmetic is retained in JSON; Markdown and CSV display totals are rounded. No-op cases and zero-service DSCR periods are reported explicitly.

This local portfolio draft calculates a declared volume-price-cost cash bridge. Taxes, capex, working capital and debt service are explicit inputs. It does not recalculate Excel, solve taxes or debt, assess scenario probabilities, apply covenant thresholds or validate a forecast. The core engine does not import the debt package; its optional handoff is documented explicitly.

An optional [connected demonstration](examples/README.md#executed-debt-handoff) executes both engines using explicit script/input paths, checks a one-to-one period mapping and records evidence hashes. Its sibling debt package dependency is declared; the core scenario engine remains standalone.

The unit tests establish arithmetic, isolation and validation behavior, not an agent performance benchmark. Copyright and use terms are in [LICENSE](LICENSE).
