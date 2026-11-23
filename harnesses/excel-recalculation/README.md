# Check the saved results of a financing workbook

Does a saved formula still give the right answer after a financing assumption changes? This harness builds two synthetic workbooks from the [financing pro forma](../../skills/financing-pro-forma/README.md). Each workbook compares refinancing with a capital investment. The challenge increases capital spending by USD10 million in one cell. All amounts below are USD millions.

| Result to check | Refinancing, both runs | Investment, baseline | Investment, challenge |
| --- | ---: | ---: | ---: |
| New borrowing | 120 | 120 | 120 |
| Capital spending | 0 | 100 | 110 |
| Closing cash | 168 | 168 | 158 |
| Gross debt including leases | 470 | 570 | 570 |
| Net debt including leases | 302 | 402 | 412 |
| Assets less liabilities and equity | 0 | 0 | 0 |

## Run both cases

Use Python 3.11 or newer with LibreOffice Calc available on the command path. From the repository root, run the following commands.

```sh
python -m pip install -r requirements-dev.txt
python harnesses/excel-recalculation/run.py calculate
```

The command creates two workbooks in a temporary directory. Calc uses a separate user profile and writes the calculated copies to a second directory. The JSON report identifies the engine, checks the original file hashes and gives the saved amounts for both versions.

## Inspect the evidence

Each workbook contains an **Inputs** sheet and a **Bridge** sheet. In the challenge, `Inputs!C17` moves from 100 to 110. Saved values at `Bridge!C5` and `Bridge!C11` show the change in investment-case cash and net debt. The refinancing column and the balance sheet check should hold their prior values.

The verifier checks every input, label and formula against the generated fixture. It compares all 22 saved formula results in each workbook with the independent Python financing calculation.

## Reproduce the missing-cache case

The following commands require openpyxl. From the repository root, use a new path in a scratch directory.

```sh
python harnesses/excel-recalculation/run.py prepare baseline financing-example.xlsx
python harnesses/excel-recalculation/run.py verify baseline financing-example.xlsx
python -m unittest discover -s harnesses/excel-recalculation
```

Preparation succeeds and reports `INCOMPLETE` because the new file has 22 formulas awaiting calculation. Verification returns exit code 2 for that condition and 1 for altered inputs, changed formulas or wrong saved amounts.

To check a desktop spreadsheet engine, open a copy of the prepared file, recalculate, save and close it. Run `verify baseline` on that saved copy. Repeat with `prepare challenge` and `verify challenge`. A complete match returns exit code 0 and `VERIFIED`. The local desktop Excel test encountered an add-in dialog before a verified save.

The cases cover funded closing-date transactions with ordinary worksheet formulas. They use synthetic local inputs and have no external data connections.
