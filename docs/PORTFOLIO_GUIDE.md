# Reviewing the finance and engineering work

The examples show how Noah Silverman translates a finance question into a calculation, a record of the inputs and checks a reviewer can repeat. Development and review are AI-assisted. The examples use synthetic data.

## Follow a financing decision

Start with the [closing-date financing comparison](../skills/financing-pro-forma/README.md). Both alternatives raise the same amount and leave the same cash balance. Trace the use of proceeds through the debt balance and the change in equity. The funding-gap case shows where the calculation stops when the stated sources fall short.

For a question about payment timing, use the [debt and liquidity harness](../harnesses/debt-liquidity/README.md). The combined stress leaves a surplus over the full horizon. The period ledger shows how a distribution at the first payment date changes the later funding need.

## Inspect a control that catches a mistake

The [actuals review](../harnesses/actuals-review/README.md) compares a submitted workbook with the disclosure and with the original estimate workbook. Read the cost row in the source comparison, then the growth row in the regression report. They answer different questions about the same update.

The [financing brief](case-studies/diligence-workflow.md) handles a different kind of mistake. Compare the synthetic discussion record with the automated recap. The worked brief preserves the conditions on lender interest and the outstanding diligence request.

## Inspect a calculation that can be resumed

Run the [credit review walkthrough](../harnesses/credit-review/README.md). Follow a liquidity receipt to the operating calculation and the debt schedule. Change the operating assumption and compare the two histories. Each completed attempt retains its inputs alongside its results.

## Inspect the integrations

The [data and model review](case-studies/data-and-model-review.md) shows provider formulas, missing observations and independently recomputed model results. The [MCP server guide](MCP_SERVERS.md) links to the public implementations and describes the privately held projects.

## Interpret the evidence

The [validation record](VALIDATION.md) identifies the tests, recorded outcomes and environments. The results describe the public implementations on the supplied inputs. Operating adoption, investment performance and time saved have not been measured here.
