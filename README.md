# Finance and AI Workflow Engineering

A portfolio by [Noah Silverman](https://github.com/noahsilv) of AI-assisted workflows for financial analysis, diligence and document work. Each workflow sets out the task and the checks used to review it.

The examples use synthetic data and run locally. The [workflow harnesses](harnesses/README.md) connect individual tools so a reviewer can follow a figure across files and reproduce a failed check.

Start with the [annual actuals review](harnesses/actuals-review/README.md). It catches a transposed cost figure and an undeclared change to next year's growth assumption. The original estimate workbook stays intact.

For project finance, follow the [cash at each debt payment date](harnesses/debt-liquidity/README.md). The [resumable credit review](harnesses/credit-review/README.md) shows how a changed cost assumption reaches the liquidity result and which prior calculation can be reused.

## Start with a case study

| Demonstration | Finance perspective | Engineering perspective |
| --- | --- | --- |
| [Financial analysis and model updates](docs/case-studies/financial-workflow.md) | Reconcile reported figures, examine debt and scenarios, and plan an actuals update. | Typed inputs, explicit units, immutable baselines and reproducible differences. |
| [Diligence and evidence-based briefing](docs/case-studies/diligence-workflow.md) | Track information requests and distinguish supported facts, gaps and decisions. | Stable IDs, versioned evidence, review proposals and traceable outputs. |
| [Data preparation and model review](docs/case-studies/data-and-model-review.md) | Prepare market-data formulas and audit financial results. | Preserve provider syntax, validate API responses and inspect an MCP interface. |
| [Routing and quality controls](docs/case-studies/engineering-controls.md) | Identify what can be relied on before a deliverable is used. | Capability checks, content fingerprints, stale-evidence rejection and bounded tools. |

Each case study includes generated results and the commands used to produce them. The financial inputs and outcomes are invented for the examples. They are not client work or investment recommendations.

## MCP servers

Alongside the skills, Noah built MCP (Model Context Protocol) servers that let AI assistants query data services and call another model. These projects cover financial-data retrieval and the integration work needed to use external services from an assistant.

| Project | What it does | Implementation details |
| --- | --- | --- |
| Macro-data connector bundle | Retrieves economic series and development-finance data from FRED, IMF, OECD and World Bank services, including IFC project data. | OECD dataset discovery and dimension lookup; World Bank Data360 pagination, metadata and source information on each observation. Source code remains private. |
| IATI data server | Queries published development activities, transactions and budgets through the IATI Datastore. | Publisher and country filters, paginated queries and activity-identifier checks. Source code remains private. |
| [Ultramarine model connector](https://github.com/noahsilv/ultramarine1) | Sends bounded text tasks to Ultramarine and returns candidate answers or Python proposals for host review. | Input and output limits, explicit failure responses and a separation between proposing code and executing it. The server does not execute the proposed code. |
| [Plaud recording bridge](https://github.com/noahsilv/plaudcli) | Gives an assistant read-only access to an authorized user's recordings, transcripts and notes. | OAuth token refresh, pagination and structured errors. An independent integration with Plaud's service, not the official Plaud product. |

The public repositories provide code and test suites for inspection. These descriptions were checked against source and documentation; live services were not retested for this portfolio update. Server tests are separate from this repository's skill tests. Private source code, credentials and account data are not included here.

## The skills

### Financial analysis and modelling

| Skill | Purpose |
| --- | --- |
| [Financial statement analysis](skills/financial-statement-analysis/SKILL.md) | Reconcile normalized statements and compute explicitly defined metrics. |
| [Financing pro forma](skills/financing-pro-forma/README.md) | Compare refinancing and capital spending against the same opening balance sheet. |
| [Debt schedule](skills/debt-schedule/SKILL.md) | Model defined borrowing terms and explain the resulting balance and debt service. |
| [Scenario analysis](skills/scenario-analysis/SKILL.md) | Keep the baseline explicit while comparing changes in assumptions. |
| [Actuals update planner](skills/actuals-update-planner/SKILL.md) | Turn sourced historical data into a reviewable model-update plan. |
| [Workbook tieout](skills/workbook-tieout/SKILL.md) | Reconcile mapped cells with declared periods, units and coverage. |
| [Independent model audit](skills/independent-model-audit/SKILL.md) | Recompute mapped financial outputs and report errors or missing audit coverage. |
| [Model regression testing](skills/model-regression-testing/SKILL.md) | Separate intentional changes from unexplained movement in selected outputs. |

### Diligence, evidence and documents

| Skill | Purpose |
| --- | --- |
| [Evidence ledger](skills/evidence-ledger/SKILL.md) | Preserve source-backed claims, versions and unresolved conflicts. |
| [Diligence request tracker](skills/diligence-request-tracker/SKILL.md) | Export stable requests and reconcile returned responses as proposals. |
| [Evidence brief](skills/evidence-brief/SKILL.md) | Convert supplied evidence into a concise brief with visible uncertainties and actions. |
| [Document review coverage](skills/document-review-coverage/SKILL.md) | Show which document units were reviewed and bind the record to the document version. |
| [DOCX footnotes](skills/docx-footnotes/SKILL.md) | Insert native citations within a deliberately bounded Word format. |
| [Office package audit](skills/office-package-audit/SKILL.md) | Identify structural defects and content that needs further review. |

### AI workflow controls

| Skill | Purpose |
| --- | --- |
| [Skill router](skills/skill-router/SKILL.md) | Select relevant workflows from an explicit catalog and expose missing capabilities. |
| [Artifact quality gate](skills/artifact-quality-gate/SKILL.md) | Reject missing, stale or mismatched check evidence before relying on an artifact. |
| [Prompt optimizer](skills/prompt-optimizer/SKILL.md) | Preserve intent while making a request executable and testable. |

### Financial data and integrations

| Skill | Purpose |
| --- | --- |
| [Bloomberg workbooks](skills/bloomberg-workbooks/SKILL.md) | Prepare provider-linked workbooks and distinguish saved formulas from verified data returns. |
| [Capital IQ workbooks](skills/capiq-workbooks/SKILL.md) | Preserve supplied add-in formulas in a reviewable workbook plan. |
| [Financial data retrieval](skills/financial-data-retrieval/SKILL.md) | Retrieve public observations with explicit scope, source metadata and missing-data handling. |
| [MCP API integration](skills/mcp-api-integration/SKILL.md) | Expose a bounded API through MCP tools and test requests and failure behavior. |

The Bloomberg and Capital IQ demonstrations use synthetic inputs. Live retrieval requires the relevant licensed Excel add-in and has not been verified here. API and MCP checks distinguish synthetic transport tests from calls to live services.

## What this portfolio represents

These examples come from a larger personal workflow library. They were rebuilt or adapted for public use, with synthetic data and stated limits. The Git history records the public portfolio's development, rather than the full history of the underlying work.

Development and review are AI-assisted. The workflow specifications, financial definitions, interfaces, implementation choices and validation results are available to inspect. No measured time savings, operational adoption or business impact are claimed. The [portfolio guide](docs/PORTFOLIO_GUIDE.md) explains what to look for when reviewing the finance and engineering work.

## Inspect or reproduce

Browse the case studies first. For authorized use, copy a complete folder from `skills/` into your agent's supported skill directory and read its `SKILL.md`. Technical instructions do not expand the reuse rights in the license.

The [packaged financing pro forma](downloads/financing-pro-forma.skill) includes its instructions, calculator, examples and tests. The repository check compares each file in the download with the reviewed source.

The examples use Python 3.11 or newer. Create a virtual environment, activate it and install the dependencies. In PowerShell, the activation command is `.\.venv\Scripts\Activate.ps1`. In a POSIX shell, use `. .venv/bin/activate`.

```sh
python -m venv .venv
```

After activation, run the checks from the repository root.

```sh
python -m pip install -r requirements-dev.txt
python scripts/build_catalog.py --check
python scripts/validate.py --manifest
python scripts/test.py
```

Read [validation and limitations](docs/VALIDATION.md) for the actual check results and untested capabilities. The [catalog](catalog/skills.json) provides machine-readable routing metadata. The [manifest](release-manifest.json) records source hashes; it does not certify correctness.

## Rights

All rights reserved. This is a public portfolio; see [LICENSE](LICENSE) for terms and [CONTRIBUTING.md](CONTRIBUTING.md) before proposing contributions.
