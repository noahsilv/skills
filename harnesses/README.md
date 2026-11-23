# Finance workflow harnesses

A harness runs several tools against the same synthetic case and checks the results they pass to one another. Choose a case below to inspect its inputs and expected result, or run all six together.

## Choose a case

| Runner name | Case guide | Evidence to inspect |
| --- | --- | --- |
| `actuals` | [Review an annual model update](actuals-review/README.md) | The source comparison identifies a cost discrepancy. The model comparison identifies a change in next year's growth assumption. |
| `liquidity` | [Size a cash reserve for debt payments](debt-liquidity/README.md) | The period ledger shows how much of the first surplus the project must retain to cover later shortfalls. |
| `credit` | [Resume a credit review after an assumption changes](credit-review/README.md) | The saved inputs and calculation records show which steps were reused and which were rerun. |
| `trace` | [Trace a correction to reported borrowings](financial-evidence/README.md) | Source lines, units and formulas explain which financing figures change after reclassification. |
| `workbook` | [Check saved spreadsheet results](excel-recalculation/README.md) | The portable tests catch missing or incorrect values. With LibreOffice Calc, the runner compares 44 saved results with an independent financing calculation. |
| `diligence` | [Review proposed financing terms and a returned request](../docs/case-studies/diligence-workflow.md) | The claim ledger distinguishes a sponsor request from conditional lender interest. The request tracker records the response for review. |

The liquidity case uses a [debt and operating scenario example](../skills/scenario-analysis/examples/README.md#executed-debt-handoff) to map contractual payments to operating cash by date.

## Run the checks

From the repository root, install the dependencies and run all six cases with Python 3.11 or newer.

```sh
python -m pip install -r requirements-dev.txt
python scripts/test_harnesses.py
```

To run selected cases, use the names in the table. This command returns a JSON report for the credit review and source trace.

```sh
python scripts/test_harnesses.py --case credit --case trace --json
```

Each case reports its own outcome. A failed check gives the command a nonzero exit code.

## Environment requirements

- **Workbook calculation.** With LibreOffice Calc installed, add `--with-calc` to the full run to recalculate and verify both workbooks.
- **Diligence ledger.** The temporary directory must support hard links for atomic writes. If a write is blocked, the runner reports the case and its diagnostic.
