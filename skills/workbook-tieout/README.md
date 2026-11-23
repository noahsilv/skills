# Workbook tieout

Reconcile explicitly mapped values in two Excel workbooks without changing either file. The package includes a portable agent workflow, a Python comparison helper, synthetic examples and tests.

## Compare the two workbooks

Follow the [worked example](examples/README.md) to generate a model and a source workbook. Revenue agrees after conversion from millions to thousands. Operating profit differs by USD10,000. The example returns exit code 1 because it found that mismatch.

From this package directory, install the dependencies and run the tests with Python 3.11 or newer. The requirements file pins `openpyxl==3.1.5`.

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Interpret the result

Read [the workflow](SKILL.md) for the coverage requirements and the meanings of `PASS`, `FAIL`, `INCOMPLETE` and `REVIEW`. Each result applies to the declared cell pairs. A cached formula value requires review because the helper does not recalculate the workbook. Source accuracy and whole-workbook coverage require separate checks. The helper preserves both workbooks and writes to a new report file.
