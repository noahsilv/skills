# Model regression testing

Track deliberate and unexpected movement in a model's selected outputs. Typed JSON snapshots, explicit declarations and strict coverage checks make each edit reviewable. An optional XLSX exporter creates new snapshots without saving the source workbook.

Read [SKILL.md](SKILL.md) for the workflow and [the example guide](examples/README.md) for schemas and a synthetic regression exercise.

JSON comparison uses Python 3.11+ and the standard library. Install `openpyxl==3.1.5` for XLSX export, examples and the full test suite:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
```

Neither helper recalculates formulas. Cached snapshots require review, missing values cannot pass, and only listed watch items are covered. Baselines are never edited or automatically replaced.
