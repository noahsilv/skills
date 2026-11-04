# Synthetic tieout exercise

All amounts are invented. The model has revenue of 1,250 and operating profit of 240 in USD thousands. The reference has 1.25 and 0.25 in USD millions. Revenue agrees; operating profit differs by -10 in USD thousands after the explicit conversion.

From the skill directory:

```sh
python examples/make_demo.py /tmp/tieout-example
python scripts/tieout.py /tmp/tieout-example/model.xlsx /tmp/tieout-example/source.xlsx --mapping /tmp/tieout-example/mapping.json --out /tmp/tieout-report.json
```

The comparison intentionally exits **1**, with two compared pairs and one mismatch. Use new paths on subsequent runs; generators and report writers do not overwrite existing outputs.

## Mapping schema

```json
{
  "schema_version": 1,
  "pairs": [
    {
      "id": "revenue",
      "comparison_unit": "USD thousands",
      "left": {"sheet": "Model", "cell": "B2", "period": "FY2025", "unit": "USD thousands"},
      "right": {"sheet": "Source", "cell": "D4", "period": "FY2025", "unit": "USD millions", "multiplier": 1000},
      "absolute_tolerance": 0,
      "relative_tolerance": 0
    }
  ]
}
```

Unknown fields, duplicate IDs/endpoints, nonfinite numbers, negative tolerances, zero multipliers, different declared periods and empty pair lists are rejected. A multiplier converts the stored value to the comparison basis; it is not an FX lookup. All unit and period labels are supplied declarations, not header extraction. Include currency in monetary units. For dimensionless numeric ratios use a label such as `ratio`; for exact text or boolean comparisons use `text` or `boolean`.

Only single uppercase A1 addresses are supported. Map a range as separate pairs so coverage is explicit. Dates and times compare by exact type and ISO representation. No fuzzy label matching, automatic sign inference or workbook editing occurs.

Decimal multipliers and tolerances in the mapping are parsed exactly, and arithmetic precision scales with the operands. Each numeric input is limited to 1,000 significant digits and an absolute decimal exponent of 1,000; larger inputs are rejected. Reports preserve numeric cell values, deltas and decimal mapping numbers as exact text. Workbook numbers reflect openpyxl's representation of stored Excel values, not arbitrary-precision raw XML; the helper cannot restore precision lost in Excel or another authoring application.
