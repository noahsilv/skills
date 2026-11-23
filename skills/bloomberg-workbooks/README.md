# Bloomberg workbooks

Build a Bloomberg BDP formula matrix from a list of securities and fields. The example writes four formulas for two invented securities and two fields. Controls, identifiers and field definitions occupy separate parts of the workbook.

## Build the example

Run the commands from this package directory. Choose a new output directory in a scratch location.

```sh
python -m pip install openpyxl
python scripts/build_workbook.py examples/config.json ../bloomberg-demo
python -m unittest discover -s tests -v
```

## Inspect the result

Read `report.json` before opening `workbook.xlsx`. The example records `FORMULAS_CONSTRUCTED` and `live_refresh: NOT_RUN`. Inspect the formula references and unit labels in the [saved report](examples/report.json) and [workbook inspection](examples/inspection.md).

## Provider access and scope

The tests cover formula references, blank caches, literal inputs, invalid configurations and overwrite protection. Retrieving market values requires valid identifiers, Bloomberg access and a connected licensed Excel add-in. The example covers workbook construction only. The helper generates BDP matrices. The workflow also documents BDH and BDS.

Read [SKILL.md](SKILL.md) for the workflow and [the config contract](references/config.md) for supported inputs. Bloomberg is a third-party service; this portfolio example is not an official Bloomberg product. Reuse is governed by [LICENSE](LICENSE).
