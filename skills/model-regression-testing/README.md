# Model regression testing

Compare selected model outputs and distinguish declared changes from unexpected movement. The comparison uses typed JSON snapshots, explicit declarations and strict coverage checks so each edit can be reviewed. An optional XLSX exporter creates new snapshots without saving the source workbook.

Read [SKILL.md](SKILL.md) for the workflow and [the example guide](examples/README.md) for schemas and a synthetic regression exercise.

JSON comparison uses Python 3.11+ and the standard library. Install `openpyxl==3.1.5` for XLSX export, examples and the full test suite:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
```

Neither helper recalculates formulas. Cached snapshots require review, missing values cannot pass, and only listed watch items are covered. Baselines are never edited or automatically replaced.
