# Input contract

All amounts are in whole currency units, with fractional precision chosen by `money_decimals`. There is no implicit thousands or millions scale. The currency field is a label; the engine does not look up currency minor-unit rules.

Every field shown in [terms.json](../examples/terms.json) is required. Unknown fields and duplicate JSON keys at any depth are rejected. JSON booleans, nulls and non-finite numbers are never accepted in numeric fields.

| Field | Contract |
|---|---|
| `schema_version` | Integer `1`, not a boolean. |
| `facility_id` | 1–64 ASCII letters, digits, underscores or hyphens; starts with a letter. |
| `currency` | Three uppercase letters. |
| `money_decimals` | Integer 0–6. Precision is explicit; not inferred from currency. |
| `start_date`, `maturity_date` | Calendar dates `YYYY-MM-DD`; maturity strictly follows start. |
| `commitment` | Positive decimal string. Prior draws plus modeled draws cannot exceed it. |
| `opening_balance` | Nonnegative decimal string immediately before start-date events. No pre-start accrued interest. |
| `prior_drawdowns` | Nonnegative decimal string of cumulative draws before start, including any amounts since repaid. Must be at least opening principal and at most commitment. |
| `annual_rate` | Nonnegative decimal string in annual decimal units; `"0.055"` means 5.5%. |
| `day_count` | Exactly `ACT/365F` or `ACT/360`. The denominator stays 365 or 360 even in a leap year. |
| `payment_dates` | 1–1,000 strictly increasing dates after start, ending exactly at maturity. Interest is cash-paid on these dates. |
| `events` | Up to 5,000 objects with exactly `date`, `type`, `amount`. |

An event's `type` is `drawdown` or `repayment`; its amount is a positive decimal string in the declared money precision. Event dates may be listed in any order. There can be at most one of each type per date; aggregate multiple same-type events deliberately before running. Events must be within the inclusive start/maturity range and no draw is allowed at maturity. Interest is settled separately from the principal events. No automatic amortization or balloon is generated.

Decimal strings use ordinary unsigned base-10 notation, with at most 24 whole digits and 12 fractional digits for the rate, or `money_decimals` fractional digits for amounts. Signs, exponents, commas, whitespace, leading zeroes and excess precision are rejected. Input files are limited to 1 MiB. These are implementation bounds, not financial policy limits.

For consecutive event or payment dates `a`, `b`, exact interval interest is:

```text
principal effective after events on a × annual_rate × (b − a in days) / denominator
```

The interval includes `a` and excludes `b`. Interest accrued to a payment date is rounded once, half up, to the selected money precision. The engine does not round each segment. Principal always uses the exact entered money amounts. The period's debt service is its sum of principal payments plus rounded period interest; it does not imply principal cash was all paid at the period end.
