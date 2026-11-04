# Scenario analysis: Synthetic_Connected_Operations

Amounts: USD currency units. Base preservation: PASS.

The engine recalculates its declared operating cash bridge for every case. Each case and sensitivity starts from the same base. Taxes, maintenance capex, working capital and debt service are explicit inputs and change only when overridden.

| Case | Status | Revenue | EBITDA | CFADS | Debt service | Cash after service | Minimum defined DSCR | DSCR periods |
|---|---|---:|---:|---:|---:|---:|---:|---|
| base | BASE | 2908000.00 | 1358000.00 | 1016000.00 | 649138.37 | 366861.63 | 1.226008 | 4/4 |
| volume_down | OUTPUT_CHANGED | 2471800.00 | 1098500.00 | 756500.00 | 649138.37 | 107361.63 | 0.930014 | 4/4 |
| fixed_cost_up | OUTPUT_CHANGED | 2908000.00 | 1302200.00 | 960200.00 | 649138.37 | 311061.63 | 1.169962 | 4/4 |
| combined | OUTPUT_CHANGED | 2471800.00 | 1042700.00 | 700700.00 | 649138.37 | 51561.63 | 0.873968 | 4/4 |

Amounts are totals over the declared periods. DSCR is the minimum of defined period ratios, not total CFADS divided by total debt service. A period with zero debt service has undefined DSCR; it is excluded from the minimum and disclosed in the period coverage count.

## Effective assumption changes

- base: none.
- volume_down: volume.
- fixed_cost_up: fixed_cost.
- combined: volume, fixed_cost.

Exact changes by period are in assumption_changes.csv. A case with no output movement needs interpretation: it may be a no-op or a changed assumption with no effect at the given base.

## One-factor sensitivities

Each level changes only the named assumption across all periods from base; axes are not combined.

| Axis | Assumption | Operation | Level | Cash after service | Change from base | Minimum defined DSCR |
|---|---|---|---:|---:|---:|---:|
| volume_multiplier | volume | multiply | 0.800000000000 | 20861.63 | -346000.00 | 0.831350 |
| volume_multiplier | volume | multiply | 0.900000000000 | 193861.63 | -173000.00 | 1.028679 |
| volume_multiplier | volume | multiply | 1.000000000000 | 366861.63 | 0.00 | 1.226008 |
| volume_multiplier | volume | multiply | 1.100000000000 | 539861.63 | 173000.00 | 1.423337 |
| volume_multiplier | volume | multiply | 1.200000000000 | 712861.63 | 346000.00 | 1.620665 |

Scope: one currency, volume × price revenue, variable and fixed costs, explicit cash adjustments and explicit debt service. No tax solver, debt engine, valuation, cash funding plug, probability weighting, covenant threshold or spreadsheet recalculation is performed. These results show the stated assumptions, not a forecast validation.

Base assumptions SHA-256: `4a14c4038b038a35c5b957029de2aed5778bf45befa071ac78287e5cc8180343`

Input SHA-256: `f095f56fef44c77717a9d376511923016470387c15ca3d166a632443a813f86f`
