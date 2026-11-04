# Capital IQ workbooks

Produces a cell-and-formula plan from supplied Capital IQ Pro or legacy formulas. It preserves formula text, checks declared result areas for collisions and links presentation cells to raw results.

```sh
python scripts/build_plan.py examples/config.json /tmp/capiq-plan.json
python -m unittest discover -s tests -v
```

The output must be a new file. The [saved example plan](examples/plan.json) contains a synthetic formula with an omitted argument. Its prefix and arguments are retained exactly. Its identifiers and field names are invented for construction tests, not working provider queries.

The helper checks declared layouts, not provider syntax or data truth. It does not build XLSX, call Capital IQ or write cached values. A separate workbook authoring tool and licensed Excel add-in are needed for those steps. Tests cover prefix preservation, quoted sheet references, range conflicts, output links and error handling.

Read [SKILL.md](SKILL.md), [the input contract](references/config.md) and [the provider workflow](references/workflow.md). Capital IQ and its add-ins are S&P Global products; this portfolio example is an independent workflow. Reuse is governed by [LICENSE](LICENSE).
