# Synthetic regression exercise

All data and changes in this directory are invented. A cost correction reduces operating profit and ending cash by 10. The example declaration lists only profit. The comparison therefore catches an undeclared cash change instead of assuming every downstream consequence was intended.

From this skill directory:

```sh
python scripts/regression.py examples/baseline.json examples/current.json --declarations examples/changes.json --out /tmp/regression-report.json
```

Expected exit **1 / FAIL**: one STABLE check, one EXPECTED_CHANGED profit item, and one REGRESSION cash item. A user could verify that the cash effect is correct and document it; the script cannot make that judgment. Comparing `baseline.json` with itself without declarations exits **0 / PASS**. Doing so with the example declarations exits **3 / REVIEW**, since profit was expected to change but did not.

## Snapshot schema

The example files show the complete required structure:

- `schema_version`: integer `1`.
- `label`: nonempty description of the state.
- `value_basis`: `literal` or `saved_formula_cache`. These are the only supported bases; the tool cannot attest to recalculation.
- `items`: nonempty list of objects with unique `id`, `value`, `unit`, and `period`.
- Optional `source_sha256`: lowercase 64-character SHA-256 of the source artifact.

Values may be finite JSON numbers, booleans, text or `null`. Null denotes missing information and yields INCOMPLETE. An empty string is text; do not use it to conceal missing financial data. Integer and floating-point forms are both numeric, but booleans are distinct. Arrays/objects are unsupported as values; flatten a vector to distinct IDs so no element can silently disappear. Do not mix currencies, denominations or periods under an unchanged label.

JSON decimal literals are parsed exactly, including differences beyond binary floating-point precision. Arithmetic precision scales with the operands. Each input number is limited to 1,000 significant digits and an absolute decimal exponent of 1,000; larger inputs are rejected explicitly. Reports encode fractional Decimal values as exact text and include `baseline_value_type` / `current_value_type` to distinguish them from text inputs. Reports are evidence, not reusable snapshots. Exported XLSX numbers reflect openpyxl's representation of the stored values; export cannot recover precision already lost in a workbook or its originating application.

## Declarations and tolerances

`changes.json` lists expected IDs and reasons. Unknown/duplicate IDs, empty reasons, unknown fields and duplicate JSON keys are rejected. Omitted IDs are expected unchanged. Declaring a value change does not permit a unit, period or type change.

An optional tolerance file has this structure:

```json
{
  "schema_version": 1,
  "items": [
    {"id": "operating-profit", "absolute": 0.5, "relative": 0, "reason": "Illustrative rounding to whole USD thousands"}
  ]
}
```

Both tolerance values must be finite, nonnegative numbers, and only numeric baseline items may have tolerances. Defaults are exact. Different calculation engines do not change tolerances automatically.

## XLSX round trip

Install the optional dependency from `requirements.txt`, then:

```sh
python examples/make_demo.py /tmp/regression-workbooks
python scripts/export_workbook.py /tmp/regression-workbooks/baseline.xlsx --watch examples/watch.json --label "Synthetic before" --out /tmp/exported-baseline.json
python scripts/export_workbook.py /tmp/regression-workbooks/current.xlsx --watch examples/watch.json --label "Synthetic after" --out /tmp/exported-current.json
python scripts/regression.py /tmp/exported-baseline.json /tmp/exported-current.json --declarations examples/changes.json --out /tmp/exported-report.json
```

The final command intentionally exits **1** with the same three outcomes. Use fresh output paths each time. The generated workbooks contain only literal synthetic values; no formula evaluation is simulated. `watch.json` supplies the explicit cell mappings. The exporter refuses missing sheets, blank cells, unsupported types and spreadsheet errors. It never saves the source workbook.
