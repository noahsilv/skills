# Normalized input and definitions

The complete machine-readable example is [complete.json](../examples/complete.json). JSON keys are case-sensitive. Unknown keys and duplicate object keys are rejected. Numbers are decimal **strings** with at most 24 integer and 12 fractional digits; JSON numbers and booleans are rejected for financial values. Exponents and NaN/Infinity are unsupported.

Required top-level fields:

| Field | Contract |
|---|---|
| `schema_version` | Integer `1`. |
| `entity` | Exactly `id`, `name`, `scope`; scope is `standalone` or `consolidated`. |
| `currency` | Declared uppercase three-letter currency code. No currency lookup or conversion is performed. |
| `scale` | `"1"`, `"1000"`, `"1000000"` or `"1000000000"`; shared by every monetary field in every period. |
| `reporting_basis` | Explicit text identifying the accounting/measurement basis. |
| `sign_convention` | `expenses_positive_cash_flows_signed`. |
| `reconciliation_tolerance` | Nonnegative decimal string; absolute amount in the reporting units, inclusive boundary. |
| `tolerance_reason` | Required explanation, including for exact checks. |
| `sources` | Nonempty array of `id`, `document`, `title`, `audit_status`, `sha256`; audit status is `audited`, `unaudited`, `interim` or `unknown`. The lowercase SHA-256 is a declared source identity, not verified by this helper. |
| `periods` | 1–50 period objects described below. |

IDs start with an ASCII letter and contain letters, digits, underscores or hyphens, up to 80 characters. Source IDs and period IDs must be unique. Text has a 2,000-character limit and cannot contain control characters. The whole input is limited to 5 MB.

A period has exactly `id`, `label`, `start`, `end`, `kind`, `basis`, `values`. Dates use ISO `YYYY-MM-DD`, are inclusive, ordered, and cover at most 372 days. Kind is `annual` (350–372 days) or `interim`. Basis is `as_reported` or `restated`. Duplicate date coverage is rejected even if labels or basis differ: select one source vintage first. Overlapping annual and interim coverage can be presented separately; the helper does not aggregate or compare them.

`values` is a nonempty object using only the fields below. Each entry has exactly:

```json
{
  "value": "120.25",
  "sources": [{"source_id": "filing25", "locator": "physical page 4, balance sheet"}],
  "note": ""
}
```

A supplied number needs at least one valid source reference. A missing entry uses `"value": null`, a nonempty `note`, and may have an empty `sources` array. Absent fields are reported separately. Every needed undisclosed component, including a lease balance or FX movement, remains unknown unless a supported zero is supplied.

## Fields and identities

All amounts share entity, scope, currency, scale and the period's selected vintage. Balance-sheet fields refer to the end date. Opening cash/equity refer to the beginning of the period; income, flows and owner movements cover the inclusive date range. Net income and other comprehensive income must cover the same ownership scope as total equity.

| Fields | Meaning and convention |
|---|---|
| `total_assets`, `total_liabilities`, `total_equity` | Reported balance-sheet totals. Assets and liabilities are nonnegative; equity may be negative. |
| `current_assets`, `current_liabilities` | Reported current balances, nonnegative. |
| `cash_and_equivalents` | Balance-sheet cash on the same definition as the cash-flow closing balance; nonnegative. Resolve overdraft/restricted-cash differences before using the direct tie. |
| `debt_current`, `debt_noncurrent` | Interest-bearing borrowings, including bonds/notes, **excluding all leases**; each maturity class is non-overlapping and nonnegative. |
| `leases_current`, `leases_noncurrent` | Lease obligations excluded from the debt fields above, nonnegative. Document debt classification in notes. |
| `revenue`, `gross_profit`, `operating_profit`, `net_income` | Reported income lines, signed as reported. No EBITDA is inferred from missing depreciation. |
| `cost_of_sales`, `operating_expenses` | Positive deductions; operating expenses exclude costs already included in cost of sales. |
| `opening_cash`, `closing_cash` | Cash-flow balances on the same definition, nonnegative. |
| `cash_from_operations`, `cash_from_investing`, `cash_from_financing`, `fx_cash_movement` | Signed net flows/effect; inflows positive, outflows negative. |
| `opening_equity`, `other_comprehensive_income` | Signed equity opening amount and other comprehensive income. |
| `owner_contributions`, `dividends` | Nonnegative owner contributions and distributions deducted from equity. If additional equity movements exist, this bounded identity is incomplete: do not force a plug. |

Every check calculates a residual, and passes only if all inputs exist and `abs(residual) <= tolerance`:

1. `total_assets − total_liabilities − total_equity`.
2. `gross_profit − revenue + cost_of_sales`.
3. `operating_profit − gross_profit + operating_expenses`.
4. `closing_cash − opening_cash − cash_from_operations − cash_from_investing − cash_from_financing − fx_cash_movement`.
5. `cash_and_equivalents − closing_cash`.
6. `total_equity − opening_equity − net_income − other_comprehensive_income − owner_contributions + dividends`.

The identities intentionally cover a limited set of presentations. For a bank without a conventional gross-profit line, or a company with more complex equity movements, report incomplete coverage and choose an appropriate separate analysis. Do not relabel lines to make the checks pass.

## Metric definitions

| Metric | Formula | Output unit |
|---|---|---|
| Gross margin | gross profit / revenue | fraction |
| Operating margin | operating profit / revenue | fraction |
| Net margin | net income / revenue | fraction |
| Operating cash margin | operating cash flow / revenue | fraction |
| Current ratio | current assets / current liabilities | multiple |
| Gross debt | current + noncurrent borrowings + current + noncurrent leases | reporting units |
| Net debt | gross debt − cash and equivalents | reporting units |
| Debt/equity | gross debt / total equity | multiple |

`0.250000` is a 25% margin. Monetary arithmetic uses precision 80 with no amount rounding; ratios use six decimal places and half-even rounding. Zero/negative denominators are `UNDEFINED`, missing inputs are `UNKNOWN`, and all input references are retained in the result. A calculation can coexist with failed accounting checks; inspect both. The helper sets no analytical benchmark, covenant limit, valuation conclusion or debt-service coverage estimate.
