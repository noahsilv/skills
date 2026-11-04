---
name: model-regression-testing
description: Detect unexpected changes to a model's watched outputs using immutable JSON snapshots, explicit intended-change declarations and typed comparisons. Use before and after actuals updates, formula edits, scenario rewiring or other changes to an already reviewed model. Includes an optional read-only XLSX exporter.
compatibility: Python 3.11+; JSON comparison uses the standard library. Optional XLSX export requires openpyxl 3.1.5.
---

# Model regression testing

Turn a model edit into a reviewable change record. A baseline is a record of a reviewed state, not evidence that the model was correct. This workflow detects changes in selected outputs; it does not certify the model or inspect unlisted cells.

## Workflow

1. **Choose coverage.** Name the outputs that should stay stable or change: headline results, balances, key assumptions and control flags. Use explicit IDs, units and periods. Avoid auto-selected watch lists that silently omit important outputs. Document exclusions.
2. **Capture the baseline before editing.** Use the [snapshot schema and examples](examples/README.md). For an XLSX workbook, export an explicit watch map with the optional helper. Check the exported values against the reviewed model. Keep the baseline file unchanged.
3. **Declare expected changes before making them.** List each watched ID expected to move and a concrete reason in a separate declarations file. Unlisted IDs are expected to stay unchanged. A declaration is not approval of any resulting number.
4. **Make the authorized edit and capture a new snapshot.** Recalculate in the appropriate spreadsheet engine when needed. Preserve the calculation evidence separately; neither bundled helper calculates formulas or verifies the engine's results.
5. **Compare and investigate.** Run the command below. Unexpected movement, missing/added IDs, type changes and changed unit/period labels fail the comparison. Expected changes and expected-but-unchanged values require review. If an edit was made without a declaration, record that limitation and review the actual differences; do not backdate a plan.
6. **Retain the evidence.** Fix errors and repeat with a new snapshot/report. Once intended changes have been checked, explicitly designate a new baseline under a new filename. Retain the prior baseline, declarations and reports. No helper automatically re-baselines or approves changes.

```sh
python scripts/regression.py baseline.json current.json --declarations changes.json --out report.json
```

Omit `--declarations` to expect every watched item to remain unchanged. An optional `--tolerances tolerances.json` supplies justified numeric tolerances; otherwise comparison is exact. Allowed difference is `max(absolute, relative × abs(baseline))`. There is no automatic tolerance widening or hidden near-zero denominator.

## Interpret the report

| Exit | Status | Meaning |
|---|---|---|
| 0 | PASS | All listed literal values are stable; there are no declared changes or coverage defects. |
| 1 | FAIL | Unexpected change, added/removed item, changed type or changed unit/period basis. |
| 2 | INCOMPLETE | Invalid input or a missing value; review other findings as well. |
| 3 | REVIEW | Expected changes, changes that did not occur, or unverified formula caches require review. |

The report lists each ID's baseline/current value, declared reason, tolerance and outcome. `EXPECTED_UNCHANGED` means an item **declared to change did not move beyond tolerance**; it is not a successful invariant check. `STABLE` means an item expected to stay fixed remained within tolerance. Numeric values compare numerically; booleans and strings retain their types. Blank/null values never pass, even when both snapshots are blank.

## Optional XLSX export

```sh
python scripts/export_workbook.py model.xlsx --watch watch.json --label "Before edit" --out baseline.json
```

The helper reads only specified single cells, records the source file's SHA-256, and writes a new snapshot. Existing destinations are refused. It supports `.xlsx`, not macros or encrypted files. Unit and period labels come from the watch map; verify them against the workbook. Dates/times require explicit normalization outside this exporter.

Mapped formulas are blocked unless `--allow-cached-values` is supplied. That flag only reads last-saved formula results. Missing caches and spreadsheet errors remain blocked. An exported snapshot containing any formula cache is marked `saved_formula_cache`; comparisons using it cannot return PASS. A hash identifies a file, not proof that its formulas were recalculated. Do not relabel cached values as literal to obtain a pass.

## Deliver

State the status, baseline/current labels, watch coverage, counts by outcome, calculation limitation, relevant deltas and paths to the evidence. Explain whether each intended change was verified independently. Do not describe a successful comparison as a full model audit.

## Validation

Run `python -m unittest discover -s tests -p 'test_*.py' -v` from this directory. The suite exercises unexpected and intended changes, removed items, strict typing, nulls, nonfinite values, invalid schemas, tolerances, cache limitations and refusal to overwrite evidence.
