# Finance and AI Workflow Engineering

A portfolio by [Noah Silverman](https://github.com/noahsilv) of AI-assisted workflows for financial analysis, diligence and document work. Each workflow sets out the task and the checks used to review it.

The workflows record what numbers mean, which sources support a claim and what still needs review. They use strict schemas, stable identifiers, routing based on available tools, and checks tied to the current file. Examples use synthetic data and can be inspected without an account or internal system.

## Start with a case study

| Demonstration | Finance perspective | Engineering perspective |
| --- | --- | --- |
| [Financial analysis and model updates](docs/case-studies/financial-workflow.md) | Reconcile reported figures, examine debt and scenarios, and plan an actuals update. | Typed inputs, explicit units, immutable baselines and reproducible differences. |
| [Diligence and evidence-based briefing](docs/case-studies/diligence-workflow.md) | Track information requests and distinguish supported facts, gaps and decisions. | Stable IDs, versioned evidence, review proposals and traceable outputs. |
| [Routing and quality controls](docs/case-studies/engineering-controls.md) | Identify what can be relied on before a deliverable is used. | Capability checks, content fingerprints, stale-evidence rejection and bounded tools. |

Each case study includes generated results and the commands used to produce them. The financial inputs and outcomes are invented for the examples. They are not client work or investment recommendations.

## The skills

### Financial analysis and modelling

| Skill | Purpose |
| --- | --- |
| [Financial statement analysis](skills/financial-statement-analysis/SKILL.md) | Reconcile normalized statements and compute explicitly defined metrics. |
| [Debt schedule](skills/debt-schedule/SKILL.md) | Model defined borrowing terms and explain the resulting balance and debt service. |
| [Scenario analysis](skills/scenario-analysis/SKILL.md) | Keep the baseline explicit while comparing changes in assumptions. |
| [Actuals update planner](skills/actuals-update-planner/SKILL.md) | Turn sourced historical data into a reviewable model-update plan. |
| [Workbook tieout](skills/workbook-tieout/SKILL.md) | Reconcile mapped cells with declared periods, units and coverage. |
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

## What this portfolio represents

These examples come from a larger personal workflow library. They were rebuilt or adapted for public use, with synthetic data and stated limits. The Git history records the public portfolio's development, rather than the full history of the underlying work.

Development and review are AI-assisted. The workflow specifications, financial definitions, interfaces, implementation choices and validation results are available to inspect. No measured time savings, operational adoption or business impact are claimed. The [portfolio guide](docs/PORTFOLIO_GUIDE.md) explains what to look for when reviewing the finance and engineering work.

## Inspect or reproduce

Browse the case studies first. For authorized use, copy a complete folder from `skills/` into your agent's supported skill directory and read its `SKILL.md`. Technical instructions do not expand the reuse rights in the license.

For the executable demonstrations, Python 3.11 or newer is the development baseline:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/build_catalog.py --check
python scripts/validate.py --manifest
python scripts/test.py
```

Read [validation and limitations](docs/VALIDATION.md) for the actual check results and untested capabilities. The [catalog](catalog/skills.json) provides machine-readable routing metadata. The [manifest](release-manifest.json) records source hashes; it does not certify correctness.

## Rights

All rights reserved. This is a public portfolio; see [LICENSE](LICENSE) for terms and [CONTRIBUTING.md](CONTRIBUTING.md) before proposing contributions.
