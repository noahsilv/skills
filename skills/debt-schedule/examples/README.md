# Synthetic facility

The [synthetic facility terms](terms.json) specify a USD750,000 non-revolving commitment, two draws totaling USD600,000, fixed interest of 5.5 percent and three repayments. The second draw falls between interest payment dates. The schedule crosses a leap year.

## Generate the schedule

Run from the package directory using a new output path.

```sh
python scripts/debt_schedule.py examples/terms.json --out /tmp/debt-schedule-example
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Check the first interest payment

Use the [accrual detail](output/accruals.csv) to trace each balance and day count into the [payment schedule](output/schedule.csv). Both files were generated from the supplied terms.

Interest accrues on USD400,000 for 104 days. After the second draw of USD200,000, it accrues on USD600,000 for 77 days. The first payment is `(400000 × 104 + 600000 × 77) × 0.055 / 365`, rounded once to cents. Later periods use the lower principal after each repayment. The final principal balance is zero and the unused commitment is USD150,000.
