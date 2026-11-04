---
name: debt-schedule
description: Build and verify a dated debt roll-forward for a fixed-rate non-revolving facility from explicit terms, drawdowns and repayments. Use for loan amortization, partial-period interest or debt-service calculations when the caller needs traceable balances and cash payments. Produces an exact accrual trail, CSV schedule and readable report; does not recalculate an Excel model.
compatibility: Python 3.11+; standard library only.
---

# Debt schedule

Turn supplied loan terms into a reproducible schedule with a visible principal reconciliation and dated interest segments. Keep the contractual currency throughout the calculation. Treat the JSON input as a record of the caller's assumptions, not proof of the loan agreement.

## Establish the contract

1. Identify the facility, currency, unit, commitment, opening principal, cumulative draws before the start, start and maturity dates, fixed annual rate, day-count convention and interest payment dates. Obtain all drawdown and repayment dates and amounts. Use [the input contract](references/input-contract.md); every field is explicit.
2. Determine whether this engine fits. It supports one non-revolving facility, simple fixed interest, positive drawdowns and repayments, ACT/365F or ACT/360, and cash interest at each payment date. Cumulative prior draws consume commitment even when some principal was repaid before the start. Prior accrued interest at the start date is zero by contract. Repayments do not restore drawing capacity.
3. Reconcile the supplied amortization schedule to full repayment at maturity. The engine rejects overpayment, excess cumulative draws and remaining maturity principal. It does not invent a balancing repayment, grace period, fee or refinancing assumption. Resolve missing terms with the caller before calculating.
4. Verify the date convention against the requested analysis: interest runs from each date inclusive to the next date exclusive. Cash events occur after accrual up to that date. A payment-date principal event appears in the period ending that day and affects interest from that day onward. On the same date, drawdowns precede repayments.

## Calculate and review

From this package's directory, use a new output directory:

```sh
python scripts/debt_schedule.py examples/terms.json --out /tmp/debt-schedule-run
```

The helper reads the input, validates every field, calculates with exact fractions and checks the input hash again before writing. Existing output paths are refused. Exit 0 means the specified calculation completed; exit 2 means invalid input or an I/O failure. On I/O failure an incomplete new output directory may remain; inspect it and choose a fresh destination.

Review all four outputs:

- `report.md`: dates, balances, interest payments, totals and scope.
- `schedule.csv`: one row per interest payment period; principal repayment includes every repayment in that period, even if paid before the period end.
- `accruals.csv`: intervals, daily principal basis and exact interest fractions.
- `report.json`: the same calculations, checks and input SHA-256.

Verify opening + draws − repayments = closing for each row and the next opening equals the prior closing. Independently recompute a first drawdown interval, one repayment interval and the final period. Interest is rounded half up once per payment period to the caller's `money_decimals`; debt service adds that cash interest to principal repayments. Sum the rounded payments to obtain total paid interest. Displayed segment interest is informational; exact fractions establish the total.

## Handoff and limits

State the currency, units, rate, convention, total drawdowns, total repayments, interest paid, final balance, input hash and output path. Describe any assumptions supplied separately from contractual evidence. A successful calculation does not validate legal terms, affordability or a whole financial model.

For a scenario comparison, calculate each changed set of terms in its own new directory. The separate `scenario-analysis` package accepts explicit period debt-service amounts; align period boundaries, currency and units, then copy `debt_service` amounts with their input/report hashes into your own handoff record. It does not import this package automatically. Rate or principal changes require recalculating this debt schedule and updating those amounts.

There is no floating-rate reset, fee, holiday adjustment, capitalization, compounding, FX, revolving facility, cash sweep, covenant or spreadsheet engine. Extend the model and its tests explicitly before claiming any of those capabilities.

## Verification

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

The tests compare hand-calculated debt service and interest, leap-year behavior, same-day events, boundary dates, payment rounding, maturity reconciliation, commitment use and strict schema rejection. They also verify input preservation and output refusal. See [the example guide](examples/README.md) for the synthetic case.
