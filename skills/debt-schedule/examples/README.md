# Synthetic facility

`terms.json` is invented for this portfolio: a USD 750,000 non-revolving commitment, two draws totaling USD 600,000, fixed 5.5% interest and three explicit repayments. The second draw occurs between interest payment dates; the schedule also crosses a leap year. No source loan, client, lender or policy terms are represented.

From the package directory:

```sh
python scripts/debt_schedule.py examples/terms.json --out /tmp/debt-schedule-example
python -m unittest discover -s tests -p 'test_*.py' -v
```

Choose a new output path for each run. The checked-in `output/` directory contains the result generated from the same JSON. It is a saved demonstration; it is not a live model.

Check the first interest period independently: USD 400,000 accrues for 104 days before the additional USD 200,000 draw, then USD 600,000 accrues for 77 days. Interest is `(400000 × 104 + 600000 × 77) × 0.055 / 365`, rounded once to cents. Later periods use the lower principal after each dated repayment. The final principal balance is zero and unused commitment is USD 150,000.
