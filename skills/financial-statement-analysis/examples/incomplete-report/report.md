# Historical statement analysis

Status: **INCOMPLETE**

Cedar Circuit Components (synthetic); consolidated; USD, scale 1000000.
Reporting basis: Fictional conventional corporate statement presentation; illustrative data only.

Source references are supplied declarations, not independently verified evidence. A complete result means only that the listed checks and metrics could be evaluated. No credit opinion or universal benchmark is assigned.
Reconciliation tolerance: 0 reporting units. Reason: Exact synthetic amounts; no rounding allowance.

## FY2025 (synthetic)

2025-01-01 to 2025-12-31; annual; as_reported; flows are not annualized.
Coverage: 24/26 fields; 5/6 checks; 5/8 metrics.
Explicit missing: leases_noncurrent. Absent: fx_cash_movement.

| Reconciliation | Status | Residual | Missing inputs |
|---|---|---:|---|
| balance_sheet | PASS | 0 | — |
| gross_profit | PASS | 0 | — |
| operating_profit | PASS | 0 | — |
| cash_rollforward | UNKNOWN | — | fx_cash_movement |
| cash_to_balance_sheet | PASS | 0 | — |
| equity_rollforward | PASS | 0 | — |

| Metric | Status | Value | Unit / reason |
|---|---|---:|---|
| gross_margin | CALCULATED | 0.437500 | fraction; calculated |
| operating_margin | CALCULATED | 0.195312 | fraction; calculated |
| net_margin | CALCULATED | 0.140625 | fraction; calculated |
| operating_cash_margin | CALCULATED | 0.144531 | fraction; calculated |
| current_ratio | CALCULATED | 2.083333 | multiple; calculated |
| gross_debt | UNKNOWN | — | reporting_units; Required values are missing |
| net_debt | UNKNOWN | — | reporting_units; Required values are missing |
| debt_to_equity | UNKNOWN | — | multiple; Required values are missing |

See report.json for normalized values, exact formulas and source references for every check and metric.

## Declared source register

| ID | Document | Audit status |
|---|---|---|
| disclosure | synthetic-disclosure.txt: Fictional FY2025 financial disclosure | audited |
