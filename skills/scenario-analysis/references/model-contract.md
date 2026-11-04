# Model and input contract

This engine evaluates a fixed operating cash bridge for one currency. Each row of the input is a full period total or a period price; dates establish coverage and alignment, not annualization. Period lengths may differ, and no day-count adjustment or growth compounding is applied to the supplied quantities.

## Equations

```text
revenue                  = volume × unit_price
variable_cost            = volume × unit_variable_cost
EBITDA                   = revenue − variable_cost − fixed_cost
CFADS                    = EBITDA − cash_taxes − maintenance_capex − working_capital_increase
cash_after_debt_service  = CFADS − debt_service
DSCR                     = CFADS / debt_service, when debt_service > 0
```

CFADS here is the engine's stated cash bridge. It is not a determination of any contract's covenant numerator. A negative working-capital increase releases cash. Negative cash results and negative defined DSCRs remain visible. A zero denominator makes DSCR undefined even if CFADS is positive. Minimum DSCR excludes undefined periods and shows coverage. This model does not include growth capex, other financing flows, opening cash, debt interest generation or a tax calculation.

Cash taxes, maintenance capex and debt service remain unchanged during a revenue stress unless explicitly overridden. This can be a deliberate case assumption or a limitation requiring a separate model. There are no hidden feedback mechanisms.

## Schema

[cases.json](../examples/cases.json) shows the complete structure. Every field is required; unknown fields, duplicate JSON keys, nulls in inputs and non-finite numbers are rejected.

| Field | Contract |
|---|---|
| `schema_version` | Integer `1`; booleans are rejected. |
| `analysis_id` | ASCII identifier, 1–64 characters, beginning with a letter; subsequent characters are letters, digits, hyphens or underscores. |
| `currency` | Three uppercase letters; a label, not a currency database lookup. |
| `money_decimals` | Integer 0–6 for displayed amounts. Exact calculations are not rounded to this precision. |
| `periods` | 1–120 objects, each with unique `id`, `start_date`, `end_date`. Dates use `YYYY-MM-DD`, end follows start, and successive periods are contiguous and ordered. |
| `base_assumptions` | Exactly the eight assumption arrays below, each with one decimal string per period. |
| `cases` | 1–32 objects with unique `id` and `overrides`. First is `base` with `{}` overrides. |
| `sensitivities` | 0–16 objects with unique `id`, `assumption`, `operation`, `values`. Each has 1–21 distinct numeric levels. |

Assumption units:

| Assumption | Unit and interpretation |
|---|---|
| `volume` | Period units sold; the user must choose a consistent physical unit. |
| `unit_price` | Currency units per physical unit. |
| `unit_variable_cost` | Currency units per physical unit sold. |
| `fixed_cost` | Currency units per period. |
| `cash_taxes` | Cash taxes paid in currency units per period. |
| `maintenance_capex` | Currency units of maintenance capital spending per period. |
| `working_capital_increase` | Currency units per period; negative means a release. |
| `debt_service` | Principal plus interest and any explicitly included cash fees, in currency units per period. The caller defines and documents the inclusion basis. |

Every assumption except `working_capital_increase` must be nonnegative both at base and after overrides. `volume` and prices may be fractional. Decimal strings have optional leading minus, no exponent or thousands separator, at most 24 whole digits and 12 fractional digits, and no leading zeroes except zero itself. Booleans, JSON numeric literals and nulls are rejected in these arrays. Files are limited to 1 MiB. Bounds are engineering limits, not institutional rules.

A case's `overrides` maps assumption names to exactly `operation` and `values`. `values` has one decimal string per period. Supported operations have literal meanings:

- `replace`: applied value equals supplied value.
- `add`: applied value equals base plus supplied value, in the assumption's units.
- `multiply`: applied value equals base times supplied dimensionless multiplier.

An assumption may appear only once per case. There is no case inheritance or operation chaining. An empty non-base case or an identity override is allowed and flagged as `NO_ASSUMPTION_CHANGE`. Changed assumptions with unchanged exact period outputs receive `ASSUMPTIONS_CHANGED_OUTPUT_UNCHANGED`; other changed cases receive `OUTPUT_CHANGED`.

A sensitivity supplies a scalar list in `values`. Each scalar applies to the named assumption across every period, starting from base; the next scalar starts from base again. Axes are independent, not a Cartesian product. No correlations or probabilities are assumed.

## Arithmetic and report interpretation

Inputs become exact rational numbers. No intermediate arithmetic is rounded. Money displays use half-up rounding; displayed ratios use six decimal places. Totals and deltas are calculated from exact results before display rounding, so the sum of individually rounded period displays can differ from a displayed total. `report.json` exposes exact fractions for review. `assumption_changes.csv` also uses exact fractions to avoid losing an override through rounding.

Input SHA-256 covers the original UTF-8 file bytes. Base-assumption SHA-256 covers the base JSON object serialized with sorted keys and compact separators; decimal strings retain their spelling. Neither hash asserts that the assumptions are correct. Reports are valid snapshots only for those inputs and this declared model version.

## Debt-schedule handoff

The optional sibling `debt-schedule` package calculates a fixed-rate facility. Neither package imports or calls the other. To use its output:

1. Run the debt engine and read `schedule.csv` and its report. Check the facility currency and that values are whole currency units.
2. Align the scenario period date bounds to the debt schedule. If multiple full debt periods make one scenario period, sum their exact currency-precision `debt_service` values. Do not proportionally split an interest payment or move a dated principal payment without an explicit cash-timing rule.
3. Enter these amounts as `base_assumptions.debt_service`. Record the originating report and input hashes, facilities included and mapping in your own case notes. The scenario file does not import or verify that external evidence.
4. For changed loan terms, run a separate debt calculation. Replace the affected case's debt-service array with its mapped payments, then rerun scenario analysis. There is no `interest_rate` scenario lever because debt service is an exogenous input here.

The included scenario example uses invented debt-service amounts and does not claim to be linked to the debt example.
