# Finance and AI skills

Each row opens a package README with its inputs, supported tasks and examples. The `SKILL.md` in that folder gives instructions to an AI assistant. For cases that use several packages, see the [workflow harnesses](../harnesses/README.md).

## Financial analysis and modeling

| Skill | Purpose |
| --- | --- |
| [Financial statement analysis](financial-statement-analysis/README.md) | Reconcile normalized statements and compute explicitly defined metrics. |
| [Financing pro forma](financing-pro-forma/README.md) | Compare refinancing and capital spending against the same opening balance sheet. |
| [Debt schedule](debt-schedule/README.md) | Model defined borrowing terms and explain the resulting balance and debt service. |
| [Scenario analysis](scenario-analysis/README.md) | Keep the baseline explicit while comparing changes in assumptions. |
| [Actuals update planner](actuals-update-planner/README.md) | Turn sourced historical data into a reviewable model-update plan. |
| [Workbook tieout](workbook-tieout/README.md) | Reconcile mapped cells with declared periods, units and coverage. |
| [Independent model audit](independent-model-audit/README.md) | Recompute mapped financial outputs and report errors or missing audit coverage. |
| [Model regression testing](model-regression-testing/README.md) | Separate intentional changes from unexplained movement in selected outputs. |

## Diligence, evidence and documents

| Skill | Purpose |
| --- | --- |
| [Evidence ledger](evidence-ledger/README.md) | Preserve source-backed claims, versions and unresolved conflicts. |
| [Diligence request tracker](diligence-request-tracker/README.md) | Export stable requests and reconcile returned responses as proposals. |
| [Evidence brief](evidence-brief/README.md) | Convert supplied evidence into a concise brief with visible uncertainties and actions. |
| [Document review coverage](document-review-coverage/README.md) | Show which document units were reviewed and bind the record to the document version. |
| [DOCX footnotes](docx-footnotes/README.md) | Insert native citations within a deliberately bounded Word format. |
| [Office package audit](office-package-audit/README.md) | Identify structural defects and content that needs further review. |

## AI workflow controls

| Skill | Purpose |
| --- | --- |
| [Skill router](skill-router/README.md) | Select relevant workflows from an explicit catalog and expose missing capabilities. |
| [Artifact quality gate](artifact-quality-gate/README.md) | Reject missing, stale or mismatched check evidence before relying on an artifact. |
| [Prompt optimizer](prompt-optimizer/README.md) | Preserve intent while making a request executable and testable. |

## Financial data and integrations

| Skill | Purpose |
| --- | --- |
| [Bloomberg workbooks](bloomberg-workbooks/README.md) | Prepare provider-linked workbooks and distinguish saved formulas from verified data returns. |
| [Capital IQ workbooks](capiq-workbooks/README.md) | Preserve supplied add-in formulas in a reviewable workbook plan. |
| [Financial data retrieval](financial-data-retrieval/README.md) | Retrieve public observations with explicit scope, source metadata and missing-data handling. |
| [MCP API integration](mcp-api-integration/README.md) | Expose a bounded API through MCP tools and test requests and failure behavior. |

The Bloomberg and Capital IQ demonstrations use synthetic inputs. Live retrieval requires the relevant licensed Excel add-in and has not been verified here. API and MCP checks distinguish synthetic transport tests from calls to live services.

The [JSON catalog](../catalog/skills.json) lists routing aliases and required capabilities. The [financing pro forma download](../downloads/financing-pro-forma.skill) contains the reviewed package for authorized use.
