# Finance and AI Workflow Engineering

[Noah Silverman](https://github.com/noahsilv) builds AI-assisted workflows for financial modeling, credit analysis and diligence. The cases below use synthetic disclosures and transactions. Each links to the inputs, the calculation or review, and the evidence behind the result.

## Start with a case study

| Finance question | What the example shows |
| --- | --- |
| [How much cash must a project retain to service debt?](harnesses/debt-liquidity/README.md) | One stressed project generates a surplus overall but falls short at three payment dates. The cash ledger shows what can be distributed and what must be retained. |
| [Did the reported results reach the forecast model?](harnesses/actuals-review/README.md) | A source check catches a USD18 million cost discrepancy. A separate comparison catches an undeclared change in next year's growth assumption. |
| [How do two uses of the same financing change net debt?](skills/financing-pro-forma/README.md) | Both cases borrow USD120 million and close with USD168 million in cash. Closing net debt is USD302 million after refinancing and USD402 million after capital spending. |
| [Which refinancing terms were actually agreed?](docs/case-studies/diligence-workflow.md) | A financing brief distinguishes the sponsor's request, conditional lender interest and the decision to continue diligence. |

## Run the debt and liquidity case

From the repository root, run the following command with Python 3.11 or newer. This case uses the standard library.

```sh
python harnesses/debt-liquidity/run.py
```

For the combined stress, the output gives a minimum retention cap of USD62,708.23. Use the [period ledger](harnesses/debt-liquidity/README.md#read-the-combined-stress) to check it against the three later payments.

## Run the full set of cases

Each harness runs the tools for a case and checks the results they pass to one another. Install the dependencies to run all six from the repository root.

```sh
python -m pip install -r requirements-dev.txt
python scripts/test_harnesses.py
```

Use the [harness index](harnesses/README.md) to run a single case or inspect its evidence. The [validation record](docs/VALIDATION.md) gives the tested environments, results and limits.

## Explore the skills and integrations

The [skill index](skills/README.md) covers financial analysis, model review, diligence, documents and data retrieval. Each package has instructions, an example and a statement of scope. The [machine-readable catalog](catalog/skills.json) records which tools each skill needs.

Five [finance skill downloads](downloads/README.md) include their instructions, examples and tests for authorized use. The repository validator compares each archive member with the corresponding source file.

Noah also built Model Context Protocol (MCP) servers for economic data, development-finance activities and model calls. The [server guide](docs/MCP_SERVERS.md) describes the integrations and links to public implementations.

## Review the work

- **Finance reviewers** can inspect [financial analysis and model updates](docs/case-studies/financial-workflow.md) or [data preparation and model review](docs/case-studies/data-and-model-review.md).
- **Engineering reviewers** can follow a [resumable credit calculation](harnesses/credit-review/README.md), trace a [correction to its source](harnesses/financial-evidence/README.md), or inspect the [routing and quality controls](docs/case-studies/engineering-controls.md). The [portfolio guide](docs/PORTFOLIO_GUIDE.md) provides a walkthrough across cases.

These are public adaptations of a larger personal workflow library. Development and review are AI-assisted. The test results cover the named examples. Live provider refresh, native Office recalculation and business impact require separate evidence.

## Rights

Copyright Noah Silverman. All rights reserved. See the [license](LICENSE) and [contribution terms](CONTRIBUTING.md).
