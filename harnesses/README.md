# Finance workflow harnesses

A harness runs several tools against the same case and checks their handoffs. The examples use synthetic inputs. Each guide gives the command, the expected result and the evidence to inspect.

## Run the checks

From the repository root, install the dependencies and run all six cases with Python 3.11 or newer.

```sh
python -m pip install -r requirements-dev.txt
python scripts/test_harnesses.py
```

Use `--case` to select one or more cases. For example, `python scripts/test_harnesses.py --case credit --case trace --json` prints a machine-readable result for the credit and evidence workflows. Add `--with-calc` to the full run to check both saved workbooks with LibreOffice Calc installed. Each case reports its own outcome. Any failed check gives the command a nonzero exit code.

## Choose a case

The diligence case uses hard links for atomic writes to its temporary evidence ledger. Run it on a filesystem that allows them. If a restricted environment blocks a write, the runner reports the failing case and its diagnostic.

| Financial question | Harness | Evidence |
| --- | --- | --- |
| Did an annual model update use the reported figures and preserve the next-year growth assumption? | [Actuals review](actuals-review/README.md) | Source tieout and model regression for two submitted workbooks. |
| How much of an early surplus must a project retain to meet later debt payments? | [Debt and liquidity](debt-liquidity/README.md) | Period cash ledger, alternative distribution policies and a test of the minimum cash retention cap. |
| Which results can the team reuse after an operating assumption changes? | [Resumable credit review](credit-review/README.md) | Versioned attempts, source snapshots and output checks linking each result to its inputs. |
| Which financing figures change after a borrowing reclassification? | [Financial evidence trace](financial-evidence/README.md) | Source lines, units and calculated dependencies across two disclosure versions. |
| Did the spreadsheet save the right results after capital spending changed? | [Financing workbook recalculation](excel-recalculation/README.md) | Two workbooks, 44 saved formula results and an independent financing calculation. |
| Does operating cash cover each contractual payment under stress? | [Debt and operating scenarios](../skills/scenario-analysis/examples/README.md#executed-debt-handoff) | Calculated debt service mapped by payment date and a coverage ratio for each operating case. |
| Which refinancing terms did each party propose, and what evidence is still outstanding? | [Financing evidence and request return](../docs/case-studies/diligence-workflow.md) | Source-linked claims, a diligence request and a proposed response. |
