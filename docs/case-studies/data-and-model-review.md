# Data preparation and model review

These demonstrations cover provider formulas, public-data retrieval and financial checks. All example inputs are synthetic. Each example runs separately; no live market-data feed connects them.

## Prepare provider formulas

The [Bloomberg example](../../skills/bloomberg-workbooks/README.md) builds four BDP formulas for two invented securities and two fields. Its report records construction checks and an unverified refresh state. Saved numeric returns remain blank. A licensed Bloomberg session is needed to test retrieval with valid securities and fields.

The [Capital IQ example](../../skills/capiq-workbooks/README.md) produces a cell-and-formula plan. It preserves the supplied formula, including its omitted argument, and checks declared result areas for overlap. The plan can guide workbook authoring; it does not establish that the provider accepts the formula.

## Retrieve observations without inventing missing values

The [public-data example](../../skills/financial-data-retrieval/examples/README.md) replays synthetic World Bank Indicators API responses. Its [report](../../skills/financial-data-retrieval/examples/output/report.md) retains an observed zero, a positive value, a null and an omitted year. It labels the unit as caller-supplied because the fixture's metadata has no unit.

Request records and response hashes make the retrieval inspectable. Pagination is checked before the result is accepted. A fixture result describes parser behavior, not the current state of an upstream service.

## Recompute financial results

The [model-audit example](../../skills/independent-model-audit/examples/README.md) compares separate input and output blocks. In the [planted-error report](../../skills/independent-model-audit/examples/planted-errors-output/report.md), a wrong closing debt balance is carried into the following period. Reported continuity passes, but recomputation finds the error. The example also detects a wrong debt-service amount and covenant verdict.

The clean case includes a correctly reported covenant breach. Agreement with the arithmetic does not mean the loan meets its covenant. The missing-data case reports checks that could not be completed.

## Inspect an MCP interface

The [MCP integration example](../../skills/mcp-api-integration/README.md) exposes a small API through a bounded protocol implementation. Its synthetic service lets a reviewer inspect requests and failure behavior without credentials. It is separate from the MCP project descriptions in the repository README.

## Reproduce

Each linked package includes commands, expected outputs and its input contract. Run them in a new output directory. Provider refresh, native Excel recalculation and hosted MCP deployment require separate verification.
