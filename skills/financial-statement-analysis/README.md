# Financial statement analysis

Analyze historical financial statements using explicit source references and accounting reconciliations, and report missing data. The portable workflow uses a reproducible data contract with strict validation.

- Six checks cover the balance sheet, gross profit, operating profit, cash movement, cash cross-reference and equity movement.
- Eight metrics cover margins, current liquidity, gross/net debt and debt/equity. Definitions are fixed and visible; no credit-rating thresholds are assigned.
- Decimal strings preserve financial precision. Missing values, real zeros, failed checks and undefined denominators remain distinct.

Start with [SKILL.md](SKILL.md), [schema and metric definitions](references/schema.md), and [the synthetic worked cases](examples/README.md). Python 3.11+ is the only dependency.

## Run the example

From this package directory, choose a new output directory next to the package.

```sh
python scripts/analyze.py examples/complete.json --out ../statement-analysis-review
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Interpret the report

Start with the six reconciliations. A failed tieout and a missing input require different follow-up. Then inspect the metric definitions and source references before using a ratio. The analyst supplies the statement figures, source references, audit labels and currency basis. Original-document extraction, foreign exchange conversion, workbook recalculation and credit opinions require separate work.

Copyright and use terms are in [LICENSE](LICENSE).
