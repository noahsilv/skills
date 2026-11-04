---
name: independent-model-audit
description: Audit a declared debt and coverage snapshot by recomputing balances, debt service, DSCR and covenant results from mapped inputs. Use when reviewing model correctness, testing a model before freezing regression outputs, or investigating plausible-looking but inconsistent financial results. Reports every comparison and missing observation; the bundled helper does not extract or recalculate Excel files.
compatibility: Python 3.11+; standard library only.
---

# Independent model audit

Review the calculation before treating its saved result as a benchmark. Keep inputs separate from the outputs being checked. The helper rebuilds the declared arithmetic without reading the model's formulas or adopting its reported debt-service denominator.

## Agree the scope

1. Identify the model, reporting currency, amount unit and ordered periods. Confirm the cash-flow definition of CFADS and the contractual covenant operator and threshold. The helper accepts a minimum or maximum DSCR test; it supplies no policy threshold.
2. Map each input and observed output to its source cell. Read [the snapshot contract](references/snapshot-contract.md). The blocks must have the same periods, currency and amount unit. A label that matches does not prove that the underlying workbook contains the right value.
3. Extract values into the snapshot after any required spreadsheet calculation. Record the model-file SHA-256. The helper records this caller-supplied hash but does not open the workbook, verify the extraction, inspect formulas or establish cache freshness. If those steps are unavailable, state them as gaps.
4. Preserve missing evidence as null. Do not replace a missing number with zero. Supply the initial principal and, if required by the audit scope, a final-principal target. Cash interest is an input; its accrual, timing and rate are outside this engine.
5. Choose absolute amount and ratio tolerances that fit the source precision. They affect numeric comparisons, not covenant decisions. A larger tolerance permits a larger discrepancy; state it with the result.

## Recompute and compare

From this package directory, choose a new output directory:

```sh
python scripts/audit_model.py examples/planted-errors.json --out /tmp/model-audit-errors
```

The example deliberately returns exit 1 because it has findings. Exit 0 means all requested comparisons passed or were explicitly not applicable. Exit 1 means a report contains findings or incomplete evidence. Exit 2 means invalid input or an I/O failure. Existing output directories are refused. An I/O failure can leave a partial new directory; inspect it and use a fresh destination.

Read `report.md`, then use `report.json` for the exact fractions, source-cell references and per-check methods. The checks are:

- Recomputed opening and closing principal, with each period carried from the initial debt and all prior input movements.
- Nonnegative principal and debt service equal to repayment plus supplied cash interest.
- DSCR equal to CFADS divided by recomputed debt service, followed by the exact covenant comparison.
- Continuity between reported closing and next reported opening, separately from the input-based recomputation.
- Final-principal target when one was supplied, with the absence of that check disclosed.

A zero debt-service denominator makes DSCR undefined. The expected stored ratio is null and the expected covenant marker is `UNDEFINED`. Missing CFADS still leaves the ratio unverified. Missing required evidence is listed as `UNVERIFIED`, even if another observation supplies a plausible number.

## Interpret the report

`CHECKS_PASSED` means checked outputs agree within the stated tolerances. It does not mean the loan meets its covenants. The clean example correctly reports a covenant breach in its last period and passes the arithmetic checks. Read the separate breach-period list.

`FINDINGS` means at least one failed comparison; incomplete checks remain visible in the same report. `INCOMPLETE` means no failed comparison was established but evidence is missing. Review both the status and counts. A passing continuity check can coexist with a failed recomputed balance when two wrong reported values agree with each other.

Report findings before making repairs. Preserve the snapshot and report hash, explain each affected period, and separate calculation errors from missing evidence or economic shortfalls. If a repair is authorized, make it in a separate working copy and rerun the audit on a fresh snapshot.

## Independence and limits

The arithmetic is computed separately from the model's reported outputs. This package does not establish organizational independence, independent reviewers, an external audit opinion or correctness of the supplied inputs. It checks one normalized debt/coverage contract. Workbook extraction, formula dependencies, multiple facilities, interest accrual, historical statement tieouts, valuation and native spreadsheet calculation require separate work.

See [the examples](examples/README.md) for clean arithmetic, planted errors and missing data. Run the executable checks with:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```
