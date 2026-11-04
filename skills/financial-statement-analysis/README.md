# Financial statement analysis

Analyze historical financial statements using explicit source references and accounting reconciliations, and report missing data. The portable workflow uses a reproducible data contract with strict validation.

- Six checks cover the balance sheet, gross profit, operating profit, cash movement, cash cross-reference and equity movement.
- Eight metrics cover margins, current liquidity, gross/net debt and debt/equity. Definitions are fixed and visible; no credit-rating thresholds are assigned.
- Decimal strings preserve financial precision. Missing values, real zeros, failed checks and undefined denominators remain distinct.

Start with [SKILL.md](SKILL.md), [schema and metric definitions](references/schema.md), and [the synthetic worked cases](examples/README.md). Python 3.11+ is the only dependency.

```sh
python scripts/analyze.py examples/complete.json --out /tmp/statement-analysis-review
python -m unittest discover -s tests -p 'test_*.py' -v
```

The report directory must be new. The helper does not read original financial reports, extract PDFs, perform FX conversion, calculate an Excel workbook or provide a credit opinion. Source references and audit labels are reviewed user inputs. Tests demonstrate the helper's stated behavior on synthetic data; no production performance or measured business impact is claimed.

This is a local portfolio draft. The all-rights-reserved notice is in [LICENSE](LICENSE).
