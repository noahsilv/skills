# Financial analysis and model updates

The financial question is whether cash arrives when debt must be paid, and whether reported historical figures have been carried into a model consistently. The engineering problem is to keep assumptions, units, periods and evidence explicit across those steps.

## Executed debt-to-scenario demonstration

[Read the generated connected report](../../skills/scenario-analysis/examples/connected-output/handoff.md). The example calculates a synthetic fixed-rate USD facility, aligns four payment periods with an operating case, and compares operating stresses using those calculated debt payments.

| Result | Base | Combined operating stress |
| --- | ---: | ---: |
| Total debt service, USD | 649,138.37 | 649,138.37 |
| Cash after debt service, USD | 366,861.63 | 51,561.63 |
| Minimum period DSCR | 1.226008 | 0.873968 |

In the combined case, cash available for debt service falls short in three of the four periods. The shortfalls are USD8,485.62, USD21,841.10 and USD32,381.51. The first period's surplus brings total cash after debt service to USD51,561.63. The [period results](../../skills/scenario-analysis/examples/connected-output/scenario/report.json) give each payment and coverage ratio.

The handoff checks dates, currency and units and records input, code and output hashes. Operating stresses leave contractual debt service unchanged. Changing interest or amortization requires a new debt calculation and a new handoff.

Use the [scenario example instructions](../../skills/scenario-analysis/examples/README.md) to reproduce the run. Inspect [debt terms and scope](../../skills/debt-schedule/README.md) before changing assumptions.

The [debt and liquidity harness](../../harnesses/debt-liquidity/README.md) follows the cash through the payment dates. It shows how much of the first surplus must remain available to cover the three later shortfalls.

## Reported statements and actuals

A separate synthetic example demonstrates [statement reconciliation](../../skills/financial-statement-analysis/README.md) and [source-linked actuals planning](../../skills/actuals-update-planner/README.md). It preserves entity, period, currency, scale, sign and source location. Missing information remains visible rather than becoming zero.

The [annual actuals review harness](../../harnesses/actuals-review/README.md) runs the planner, then reviews two separately generated model returns. A source comparison catches a transposed cost. A comparison with the original workbook catches a change to the next year's growth assumption.

These examples demonstrate financial specification, exact calculations, explicit handoffs and testable failure states. They do not establish operating performance on real client models or native Excel recalculation.
