# Debt schedule

A portable finance workflow and exact Python engine for a single fixed-rate, non-revolving facility. It converts dated draws and repayments into reconciled balances, cash interest, debt service and an inspectable accrual trail.

Read [SKILL.md](SKILL.md), the [input contract](references/input-contract.md) and the [synthetic example](examples/README.md). Requires Python 3.11+ with no third-party dependencies.

```sh
python scripts/debt_schedule.py examples/terms.json --out /tmp/debt-schedule-run
python -m unittest discover -s tests -p 'test_*.py' -v
```

Output paths must be new. Inputs remain unchanged. Exact fractions avoid floating-point drift; only cash interest payments are rounded. Supported day counts are ACT/365F and ACT/360. The engine requires explicit full principal repayment at maturity and does not insert a plug.

This local portfolio draft is bounded: no fees, floating rates, holidays, FX, compounding, refinancing, covenants or Excel recalculation. Included tests establish arithmetic and validation behavior for the documented engine; they are not a benchmark of agent skill selection or a review of loan documentation.

Copyright and use terms are in [LICENSE](LICENSE).
