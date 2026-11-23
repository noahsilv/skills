# Capital IQ workbooks

Build a cell-by-cell plan from supplied Capital IQ Pro or legacy formulas. The planner preserves the formula text, checks whether declared result areas overlap and links presentation cells to raw results.

## Generate the plan

Run the commands from this package directory. Use a new output file in a scratch location.

```sh
python scripts/build_plan.py examples/config.json ../capiq-plan.json
python -m unittest discover -s tests -v
```

## Inspect the result

The [saved plan](examples/plan.json) contains a synthetic formula with an omitted argument. Compare it with the input to check its prefix and argument positions, then follow the presentation link back to the raw result cell. The identifiers and field names are invented for this example.

## Provider access and scope

The helper checks the declared layout and writes a JSON plan. Building the workbook requires a separate authoring tool. Validating provider syntax and retrieving live values require the licensed Excel add-in. Tests cover prefix preservation, quoted sheet references, range conflicts, output links and error handling.

Read [SKILL.md](SKILL.md), [the input contract](references/config.md) and [the provider workflow](references/workflow.md). Capital IQ and its add-ins are S&P Global products; this portfolio example is an independent workflow. Reuse is governed by [LICENSE](LICENSE).
