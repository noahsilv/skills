# Financing pro forma

Two transactions raise the same USD120 million and leave the same closing cash balance. One refinances existing debt. The other finances capital spending. How much does each add to net debt?

## Worked result

| USD millions | Opening | Refinance | Capital spending |
| --- | ---: | ---: | ---: |
| Cash and equivalents | 150 | 168 | 168 |
| Borrowings excluding leases | 390 | 410 | 510 |
| Lease liabilities | 60 | 60 | 60 |
| Gross debt including leases | 450 | 470 | 570 |
| Net debt including leases | 300 | 302 | 402 |
| Total equity | 650 | 648 | 648 |

The refinancing uses USD100 million of the draw to repay borrowings. The capital-spending case buys USD100 million of assets and leaves the existing debt outstanding. Each case pays a USD2 million closing expense. These are hypothetical transactions for a synthetic company.

## Run the comparison

From this skill's directory, use Python 3.11 or newer. The calculator uses the standard library and writes to a new output file.

```sh
python scripts/bridge.py bridge examples/opening.json examples/transactions.json --out comparison-run.json
```

Inspect the [opening position](examples/opening.json), [transaction assumptions](examples/transactions.json) and [recorded comparison](examples/comparison.json). Each case starts from the same source balances. The report records the input hashes and the closing balance sheet.

## Reproduce a financing gap

```sh
python scripts/bridge.py bridge examples/opening.json examples/unfunded.json --out gap-run.json
```

The third case proposes USD300 million of capital spending and a USD2 million closing expense. Opening cash and new borrowing provide USD270 million. The report shows a USD32 million gap and leaves closing balances and ratios uncalculated. The command exits with code 1.

## Use another opening position

Supply the fields in the [input contract](references/contract.md). A complete financial-statement analysis report can also supply the opening position.

```sh
python scripts/bridge.py prepare statement-report.json --period fy2025 --out opening-run.json
python -m unittest discover -s tests -p "test_*.py"
```

## Scope

The closing-date bridge uses one currency and treats reported cash and equivalents as available for the modeled uses. Leases stay outstanding. The cash expense is recognized immediately with no tax effect. Timing, restricted cash and other accounting treatments can change the funding need.

The [workflow instructions](SKILL.md) cover source review and interpretation. The [license](LICENSE) sets the terms for reuse.
