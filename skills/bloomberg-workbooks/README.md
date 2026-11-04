# Bloomberg workbooks

Builds a BDP formula matrix with separate controls, identifiers and field definitions. The example creates four provider formulas for two invented securities and two fields. No market values are supplied.

This demonstrates formula construction, unit labels and a clear refresh boundary. BDH and BDS workflows are documented; the helper generates BDP matrices only.

```sh
python -m pip install openpyxl
python scripts/build_workbook.py examples/config.json /tmp/bloomberg-demo
python -m unittest discover -s tests -v
```

The output directory must be new. Read the generated `report.json` before opening `workbook.xlsx`. The [saved example report](examples/report.json) and [workbook inspection](examples/inspection.md) were produced by the included example.

Tests check formula references, blank caches, literal inputs, invalid configs and refusal to overwrite outputs. They do not establish provider availability or native Excel behavior. Bloomberg access and the connected licensed add-in are needed to retrieve data. The identifiers are deliberately synthetic and will not establish a valid security lookup.

Read [SKILL.md](SKILL.md) for the workflow and [the config contract](references/config.md) for supported inputs. Bloomberg is a third-party service; this portfolio example is not an official Bloomberg product. Reuse is governed by [LICENSE](LICENSE).
