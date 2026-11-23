# Finance and AI Workflow Engineering

[Noah Silverman](https://github.com/noahsilv) builds AI-assisted workflows for financial modeling, credit analysis and diligence. This portfolio uses synthetic companies, transactions and disclosures. The examples run locally.

## Start with a case study

| Finance question | What the example shows |
| --- | --- |
| [How much cash must a project retain to service debt?](harnesses/debt-liquidity/README.md) | One stressed project generates a surplus overall but falls short at three payment dates. The cash ledger shows what can be distributed and what must be retained. |
| [Did the reported results reach the forecast model?](harnesses/actuals-review/README.md) | A source check catches a USD18 million cost discrepancy. A separate comparison catches an undeclared change in next year's growth assumption. |
| [How do two uses of the same financing change net debt?](skills/financing-pro-forma/README.md) | Two cases borrow USD120 million and close with the same cash balance. Repaying existing debt and buying assets produce different closing balance sheets. |
| [Which refinancing terms were actually agreed?](docs/case-studies/diligence-workflow.md) | A financing brief distinguishes the sponsor's request, conditional lender interest and the decision to continue diligence. |

## Run a harness

A harness runs the tools for a case and checks the handoffs. The debt and liquidity example needs Python 3.11 or newer and uses the standard library. Run it from the repository root.

```sh
python harnesses/debt-liquidity/run.py
```

For the combined stress, the output gives a minimum retention cap of USD62,708.23. Use the [period ledger](harnesses/debt-liquidity/README.md#read-the-combined-stress) to check it against the three later payments.

To run the six finance cases together, install the Python dependencies and run the portfolio checks.

```sh
python -m pip install -r requirements-dev.txt
python scripts/test_harnesses.py
```

The [harness index](harnesses/README.md) lists each case, its command and its evidence. For the engineering behind a financing review, follow a [source correction](harnesses/financial-evidence/README.md), [resume a credit calculation](harnesses/credit-review/README.md) or [check the saved workbook results](harnesses/excel-recalculation/README.md).

## The skills

The [skill index](skills/README.md) covers financial analysis, model review, diligence, documents and data retrieval. Each package has instructions, an example and a statement of scope. The [machine-readable catalog](catalog/skills.json) records which tools each skill needs.

For authorized use, the [financing pro forma download](downloads/financing-pro-forma.skill) includes the calculator, examples and tests. The repository validator compares each archive member with the corresponding source file.

## MCP servers

Noah also built Model Context Protocol (MCP) servers for economic data, development-finance activities and model calls. The [server guide](docs/MCP_SERVERS.md) describes the integrations and links to public implementations.

## Inspect or reproduce

- **Finance reviewers** can inspect [financial analysis and model updates](docs/case-studies/financial-workflow.md) or [data preparation and model review](docs/case-studies/data-and-model-review.md).
- **Engineering reviewers** can inspect [routing and quality controls](docs/case-studies/engineering-controls.md), the [hiring-team guide](docs/PORTFOLIO_GUIDE.md) and the [validation results and test commands](docs/VALIDATION.md).

These are public adaptations of a larger personal workflow library. Development and review are AI-assisted. The test results cover the named examples. Live provider refresh, native Office recalculation and business impact require separate evidence.

## Rights

Copyright Noah Silverman. All rights reserved. See the [license](LICENSE) and [contribution terms](CONTRIBUTING.md).
