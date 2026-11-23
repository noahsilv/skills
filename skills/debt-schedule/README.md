# Debt schedule

Calculate balances, cash interest and debt service for a single fixed-rate, non-revolving facility. The portable workflow and exact Python engine use dated draws and repayments and provide an accrual trail for review.

Read [SKILL.md](SKILL.md), the [input contract](references/input-contract.md) and the [synthetic example](examples/README.md). Requires Python 3.11+ with no third-party dependencies.

## Run the example

From this package directory, choose a new output directory next to the package.

```sh
python scripts/debt_schedule.py examples/terms.json --out ../debt-schedule-run
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Read the results

Follow each dated draw and repayment to the closing principal balance, then check the accrued interest against the cash payment. The engine keeps exact fractions until it rounds interest payments. It supports ACT/365F and ACT/360 and requires the terms to specify full principal repayment at maturity.

## Scope

The schedule covers simple fixed-rate debt in one currency. Fees, floating rates, holiday adjustment, compounding, refinancing, covenants and workbook recalculation fall outside the calculation.

Copyright and use terms are in [LICENSE](LICENSE).
