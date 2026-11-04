# Debt schedule: Synthetic_Facility

Amounts: USD currency units. Fixed annual rate: 0.055. Day count: ACT/365F.

Interest accrues on actual calendar days, start inclusive and end exclusive. Dated cash events take effect after accrual to that date; same-day drawdowns precede repayments. Events on a payment date appear in that period's principal movements and affect the next accrual interval.

Interest is paid at each listed payment date and rounded half up once per period. Debt service is principal repaid plus rounded interest; draws are excluded. Accrual fractions are exact in report.json and accruals.csv.

| End date | Opening | Draws | Repayments | Closing | Interest paid | Debt service |
|---|---:|---:|---:|---:|---:|---:|
| 2027-07-01 | 0.00 | 600000.00 | 0.00 | 600000.00 | 13230.14 | 13230.14 |
| 2028-01-01 | 600000.00 | 0.00 | 150000.00 | 450000.00 | 16635.62 | 166635.62 |
| 2028-07-01 | 450000.00 | 0.00 | 200000.00 | 250000.00 | 12341.10 | 212341.10 |
| 2029-01-01 | 250000.00 | 0.00 | 250000.00 | 0.00 | 6931.51 | 256931.51 |

Totals: drawdowns 600000.00; repayments 600000.00; interest paid 49138.37; debt service 649138.37.
Unused non-revolving commitment: 150000.00.

Checks: principal roll-forward PASS; zero principal at maturity PASS.

Scope: one fixed-rate, single-currency facility. No fee, tax, default, holiday, rate-reset, compounding, capitalization, refinancing, FX or covenant calculation. This is a calculation of the supplied terms; no term-sheet review or spreadsheet recalculation is performed.

Input SHA-256: `f02070ef25970ea7e050f7af00fe4f9c388710c0b36da6461fc840a5a40e9d33`
