# Closing-date input contract

Supply one opening position and one transaction file. Both use schema version 1 and must agree on entity, scope, ISO date, three-letter currency code and scale. Scale is the number of currency units per reporting unit and can be 1, 1,000 or 1 million.

## Opening position

Use the [synthetic opening position](../examples/opening.json) as the schema. Decimal amounts are strings. The calculator accepts up to 18 whole digits and six decimal places. Explicit zero is an amount. Missing values stop the calculation.

| Field group | Required basis |
| --- | --- |
| Total assets, liabilities and equity | Assets equal liabilities plus equity. Negative equity is permitted. |
| Current assets and cash | Cash and equivalents are included in current assets. |
| Current liabilities | Include current borrowings and current lease liabilities. |
| Current and noncurrent debt | Borrowings exclude leases. Repayments apply to existing borrowings in the specified maturity class. |
| Current and noncurrent leases | Include each lease liability once. Both classes remain outstanding at closing. |
| Source | Supply a label, SHA-256 for the source and a locator for each opening amount. The preparer verifies transcription and source authenticity. |

When importing a statement report, select one period ID. The importer checks the report's completion status and balance-sheet check, copies the selected normalized balances and preserves their source locators. It hashes the supplied report.

## Transaction cases

Use a distinct case ID and a nonnegative amount for every flow in the [transaction file](../examples/transactions.json). A zero declares that the flow is absent from that case.

| Flow | Closing-date treatment |
| --- | --- |
| Current and noncurrent draws | Increase cash and borrowings in the stated class. |
| Current and noncurrent repayments | Reduce cash and existing borrowings in the stated class. |
| Equity contribution | Increases cash and total equity. |
| Capital spending | Moves cash into noncurrent assets. |
| Cash expense | Reduces cash and total equity. |

The bridge returns one of two case results. A balanced case includes closing balances and ratios. A funding-gap case gives the amount needed to bring cash to zero and leaves the closing position open.

## Read the metrics

Gross debt includes borrowings and lease liabilities. Net debt deducts cash and equivalents from gross debt. Gross debt to equity divides gross debt by positive equity. The current ratio divides current assets by positive current liabilities. Ratios use six decimal places. Money stays in the declared reporting units.

The command exits with code 0 when all cases balance, 1 when any case has a funding gap and 2 for an invalid input or unavailable output destination.
