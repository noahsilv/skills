# Scenario analysis: Synthetic_Operations

Amounts: USD currency units. Base preservation: PASS.

The engine recalculates its declared operating cash bridge for every case. Each case and sensitivity starts from the same base. Taxes, maintenance capex, working capital and debt service are explicit inputs and change only when overridden.

| Case | Status | Revenue | EBITDA | CFADS | Debt service | Cash after service | Minimum defined DSCR | DSCR periods |
|---|---|---:|---:|---:|---:|---:|---:|---|
| base | BASE | 1520000.00 | 645000.00 | 465000.00 | 255000.00 | 210000.00 | 1.687500 | 3/3 |
| volume_down | OUTPUT_CHANGED | 1292000.00 | 511350.00 | 331350.00 | 255000.00 | 76350.00 | 1.181250 | 3/3 |
| fixed_cost_up | OUTPUT_CHANGED | 1520000.00 | 608100.00 | 428100.00 | 255000.00 | 173100.00 | 1.537500 | 3/3 |
| combined | OUTPUT_CHANGED | 1292000.00 | 474450.00 | 294450.00 | 255000.00 | 39450.00 | 1.031250 | 3/3 |
| capex_step | OUTPUT_CHANGED | 1520000.00 | 645000.00 | 455000.00 | 255000.00 | 200000.00 | 1.562500 | 3/3 |

Amounts are totals over the declared periods. DSCR is the minimum of defined period ratios, not total CFADS divided by total debt service. A period with zero debt service has undefined DSCR; it is excluded from the minimum and disclosed in the period coverage count.

## Effective assumption changes

- base: none.
- volume_down: volume.
- fixed_cost_up: fixed_cost.
- combined: volume, fixed_cost.
- capex_step: maintenance_capex.

Exact changes by period are in assumption_changes.csv. A case with no output movement needs interpretation: it may be a no-op or a changed assumption with no effect at the given base.

## One-factor sensitivities

Each level changes only the named assumption across all periods from base; axes are not combined.

| Axis | Assumption | Operation | Level | Cash after service | Change from base | Minimum defined DSCR |
|---|---|---|---:|---:|---:|---:|
| volume_multiplier | volume | multiply | 0.800000000000 | 31800.00 | -178200.00 | 1.012500 |
| volume_multiplier | volume | multiply | 0.900000000000 | 120900.00 | -89100.00 | 1.350000 |
| volume_multiplier | volume | multiply | 1.000000000000 | 210000.00 | 0.00 | 1.687500 |
| volume_multiplier | volume | multiply | 1.100000000000 | 299100.00 | 89100.00 | 2.025000 |
| volume_multiplier | volume | multiply | 1.200000000000 | 388200.00 | 178200.00 | 2.362500 |
| price_multiplier | unit_price | multiply | 0.900000000000 | 58000.00 | -152000.00 | 1.125000 |
| price_multiplier | unit_price | multiply | 1.000000000000 | 210000.00 | 0.00 | 1.687500 |
| price_multiplier | unit_price | multiply | 1.100000000000 | 362000.00 | 152000.00 | 2.250000 |

Scope: one currency, volume × price revenue, variable and fixed costs, explicit cash adjustments and explicit debt service. No tax solver, debt engine, valuation, cash funding plug, probability weighting, covenant threshold or spreadsheet recalculation is performed. These results show the stated assumptions, not a forecast validation.

Base assumptions SHA-256: `24eda9569ddea30de17ff24ccd8faf41b55b850432705a7f0ec37d4688fc1daf`

Input SHA-256: `78cded8bad05a989f1b0d56c2bc86143978b5e947d093d814c78e0f34265cd51`
