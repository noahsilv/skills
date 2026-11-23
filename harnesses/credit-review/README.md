# Resume a credit review after assumptions change

A reviewer changes the cost assumptions after the debt schedule is complete. Which results can the team keep, and which must it calculate again?

This harness runs three local finance steps. Each completed step gets a receipt in SQLite. The receipt identifies the input versions, the calculation code, the upstream attempt and the output files.

## Run the worked revision

From the repository root, run the walkthrough with Python 3.11 or newer. It uses the standard library.

```sh
python harnesses/credit-review/demo.py
```

The walkthrough stops after calculating debt, resumes through liquidity, then lowers the fixed-cost stress from 15 percent to 10 percent. The volume stress stays at 15 percent. The debt terms stay the same.

| Step | After the cost change | After the refresh |
| --- | --- | --- |
| Debt schedule | Current | Reuses the first calculation |
| Operating scenarios | Stale | Remaps debt service and recalculates operating cash |
| Liquidity | Waits for operating scenarios | Recomputes the cash needed at payment dates |

In the combined stress, the minimum cash retention cap falls from USD62,708.23 to USD48,608.23. The run records five completed attempts. The original and revised operating assumptions remain available in their respective attempt folders. Inspect the [expected result](expected.json) or the [liquidity calculation](../debt-liquidity/README.md).

## Inspect the receipts

Keep the walkthrough in a new folder outside the checkout.

```sh
python harnesses/credit-review/demo.py --out ../credit-walkthrough
python harnesses/credit-review/run.py history ../credit-walkthrough
python harnesses/credit-review/run.py receipt ../credit-walkthrough liquidity
python harnesses/credit-review/run.py verify ../credit-walkthrough
```

Start at the latest liquidity receipt. Its `parent_id` points to the operating calculation that supplied the cash flows. That receipt points to the debt schedule. Each receipt records the run ID, UTC recording time, Python runtime and SHA-256 hashes for the files it used and produced.

## Run the steps yourself

```sh
python harnesses/credit-review/run.py init ../credit-case
python harnesses/credit-review/run.py advance ../credit-case --through debt
python harnesses/credit-review/run.py status ../credit-case
python harnesses/credit-review/run.py advance ../credit-case
```

Edit the copied assumptions in `../credit-case/inputs/operations.json` to try a different cost stress. Check the status before refreshing the affected steps.

```sh
python harnesses/credit-review/run.py status ../credit-case
python harnesses/credit-review/run.py advance ../credit-case --refresh
python harnesses/credit-review/run.py verify ../credit-case
```

| Command | What to inspect |
| --- | --- |
| `status` | The latest attempt for each step, its evidence folder and the reason for its status. Add `--json` for machine-readable output. |
| `advance` | Runs ready steps. A current step reuses its receipt. A stale or failed step requires an explicit refresh. |
| `verify` | Rechecks the current files. It exits with code 1 if any step lacks current evidence. |
| `history` | All recorded attempts in order, including failed calculations and the input hashes used in each. |

## What the checks establish

The harness copies each step's financial inputs into its attempt folder. Each new calculation reads those snapshots. Changing a source input, calculation script or recorded output invalidates the affected step. A downstream calculation waits until its upstream evidence is current.

SQLite serializes writers while each step runs. An interrupted transaction can leave an unregistered attempt folder. Resuming starts a fresh attempt, and the history includes only committed receipts.

The run covers three predefined local calculations. Receipts establish file identity and execution history. Financial assumptions, source authenticity and the credit decision require a reviewer.
