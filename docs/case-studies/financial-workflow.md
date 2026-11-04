# Financial analysis and model updates

The financial question is whether cash arrives when debt must be paid, and whether reported historical figures have been carried into a model consistently. The engineering problem is to keep assumptions, units, periods and evidence explicit across those steps.

## Executed debt-to-scenario demonstration

[Read the generated connected report](../../skills/scenario-analysis/examples/connected-output/handoff.md). The example calculates a synthetic fixed-rate USD facility, aligns four payment periods with an operating case, and compares operating stresses using those calculated debt payments.

| Result | Base | Combined operating stress |
| --- | ---: | ---: |
| Total debt service, USD | 649,138.37 | 649,138.37 |
| Cash after debt service, USD | 366,861.63 | 51,561.63 |
| Minimum period DSCR | 1.226008 | 0.873968 |

Positive total cash does not imply adequate cash generation in every payment period. In the combined case, one period's cash available for debt service is less than that period's debt payment. This is an arithmetic observation, not an assumed covenant or a credit conclusion.

The handoff checks dates, currency and units and records input, code and output hashes. Operating stresses leave contractual debt service unchanged. Changing interest or amortization requires a new debt calculation and a new handoff.

Use the [scenario example instructions](../../skills/scenario-analysis/examples/README.md) to reproduce the run. Inspect [debt terms and scope](../../skills/debt-schedule/README.md) before changing assumptions.

## Reported statements and actuals

A separate synthetic example demonstrates [statement reconciliation](../../skills/financial-statement-analysis/README.md) and [source-linked actuals planning](../../skills/actuals-update-planner/README.md). It preserves entity, period, currency, scale, sign and source location. Missing information remains visible rather than becoming zero.

The planner produces proposed edits and variances. It does not save or recalculate the workbook. The existing [tieout](../../skills/workbook-tieout/README.md) and [regression](../../skills/model-regression-testing/README.md) packages show complementary checks on mapped cells and selected outputs.

These examples demonstrate financial specification, exact calculations, explicit handoffs and testable failure states. They do not establish operating performance on real client models or native Excel recalculation.
