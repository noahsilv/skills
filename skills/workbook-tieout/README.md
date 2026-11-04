# Workbook tieout

An explicit, read-only reconciliation between two Excel workbooks. The package includes a portable agent workflow, a Python comparison helper, synthetic examples and tests.

Read [SKILL.md](SKILL.md) for the workflow, coverage requirements and interpretation of PASS, FAIL, INCOMPLETE and REVIEW. Follow [the example guide](examples/README.md) to generate a deliberate mismatch and see the report.

Requires Python 3.11+ and `openpyxl==3.1.5`:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
```

The helper does not calculate formulas. Formula caches remain unverified and cannot produce PASS. It compares only declared pairs and cannot certify source accuracy or whole-workbook coverage. Source workbooks and existing report files are never overwritten.
