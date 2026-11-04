# Snapshot contract

The root object uses schema version 1. Unknown fields, duplicate JSON keys and mismatched block metadata are rejected. Input is limited to 2,000,000 bytes and 20 nesting levels. There are 1 to 500 periods.

| Root field | Meaning |
| --- | --- |
| `schema_version` | Integer 1. |
| `model_id` | Identifier using letters, digits, hyphens or underscores, up to 80 characters. |
| `model_sha256` | Caller-supplied lowercase SHA-256 of the model. The helper does not verify the model file. |
| `currency` | Three uppercase letters; no exchange-rate conversion occurs. |
| `amount_unit` | `units`, `thousands` or `millions`; all money values use this scale. |
| `periods` | Ordered objects with unique `id`, ISO `start` and `end` dates. Intervals are consecutive, start inclusive and end exclusive. |
| `initial_debt` | Nonnegative principal before the first period's movements. |
| `required_final_debt` | Nonnegative target or null when the final-principal check is not requested. |
| `money_tolerance` | Nonnegative absolute tolerance in the declared amount unit. |
| `ratio_tolerance` | Nonnegative absolute tolerance for DSCR, measured as a ratio rather than a percentage. |
| `covenant` | Exactly `operator` (`gte` or `lte`) and `threshold` (nonnegative ratio or null when unavailable). |
| `inputs`, `observed` | Separate mapped blocks described below. |

All financial numbers are decimal strings. They may have up to 24 integer digits and 12 decimal places, without exponent notation or leading zeros. `null` means unavailable where permitted. Numeric JSON values, booleans and nonfinite values are rejected. Currency codes and cell references are labels; their truth is not established by syntax checks.

## Mapped blocks

Each block has exactly `period_ids`, `currency`, `amount_unit`, `series` and `references`. The first three must match the root metadata exactly, including period order. Each metric is an array with one entry per period. The reference array for each metric has the same length and contains caller-supplied cell labels such as `Inputs!B2`. References cannot contain Markdown controls. Missing observations still need a location identifying the expected source cell.

Inputs contain `drawdown`, `repayment`, `interest` and `cfads`. Drawdowns, principal repayments and cash interest are nonnegative magnitudes. CFADS may be negative. All four allow null. No accrual or interest calculation is inferred from the interest input.

Observed outputs contain `opening_debt`, `closing_debt`, `debt_service`, `dscr` and `covenant`. Numeric outputs allow signed numbers or null. The covenant output is `PASS`, `FAIL`, `UNDEFINED` or null. These labels describe the model's recorded conclusion, not whether the audit check passed.

## Recomputed equations

For period t:

```text
opening[t] = initial debt + sum(drawdown[earlier] - repayment[earlier])
closing[t] = opening[t] + drawdown[t] - repayment[t]
debt service[t] = repayment[t] + cash interest[t]
DSCR[t] = CFADS[t] / debt service[t], when debt service is nonzero
```

Missing debt movements make the relevant balance and subsequent balances unknown. Debt-service and ratio checks can still run if their own inputs are complete. The script never takes a reported balance as the next recomputed opening, nor a reported service amount as the recomputed ratio denominator.

A cash-flow period with zero debt service has an undefined ratio. Null observed DSCR is explicitly not applicable only when CFADS is known and service is zero. A numeric observed ratio fails that check. The corresponding covenant must be `UNDEFINED`; a missing marker is unverified. If CFADS is missing, both checks remain unverified even with zero service.

With positive service, the covenant uses the exact recomputed ratio and explicit `gte` or `lte` threshold. It never applies the numeric comparison tolerance to a legal threshold. A missing threshold leaves the covenant unverified. A loan with a correctly reported breach can receive `CHECKS_PASSED` for arithmetic; the report lists the breach periods separately.

## Results and preservation

Each check records its period, expected value, observed value, result, method and source/output references. Exact fractions are rendered as `numerator/denominator`; no floating-point conversion or display rounding drives a decision. Numeric comparisons pass when absolute difference is less than or equal to the declared tolerance. Nonnegative principal is an exact condition, without tolerance.

A failure anywhere yields `FINDINGS`. Otherwise an unverified check yields `INCOMPLETE`. Otherwise the result is `CHECKS_PASSED`. Counts show all statuses even when failures take precedence. The report separately discloses whether the optional final-principal target was checked.

The CLI saves JSON and Markdown to a new directory and records SHA-256 of the exact input bytes. It rereads the input before writing and rejects a detected change. This is a local consistency check, not protection against an adversarial writer. It never modifies the input. Write failures may leave partial outputs. Treat only a completed run as a report.

Model-file identity, cell references, extracted values and input definitions require separate verification. These checks cannot establish whole-workbook coverage or cache freshness.
