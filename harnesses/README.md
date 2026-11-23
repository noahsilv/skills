# Finance workflow harnesses

A harness runs several tools against the same case and checks their handoffs. The examples use synthetic inputs. Each guide gives the command, the expected result and the evidence to inspect.

| Financial question | Harness | Evidence |
| --- | --- | --- |
| Did an annual model update use the reported figures and preserve the next-year growth assumption? | [Actuals review](actuals-review/README.md) | Source tieout and model regression for two submitted workbooks. |
| How much of an early surplus must a project retain to meet later debt payments? | [Debt and liquidity](debt-liquidity/README.md) | Period cash ledger, alternative distribution policies and a test of the minimum cash retention cap. |
| Which results can the team reuse after an operating assumption changes? | [Resumable credit review](credit-review/README.md) | Versioned attempts, source snapshots and output checks linking each result to its inputs. |
| Which financing figures change after a borrowing reclassification? | [Financial evidence trace](financial-evidence/README.md) | Source lines, units and calculated dependencies across two disclosure versions. |
| Does operating cash cover each contractual payment under stress? | [Debt and operating scenarios](../skills/scenario-analysis/examples/README.md#executed-debt-handoff) | Calculated debt service mapped by payment date and a coverage ratio for each operating case. |
| Which refinancing terms did each party propose, and what evidence is still outstanding? | [Financing evidence and request return](../docs/case-studies/diligence-workflow.md) | Source-linked claims, a diligence request and a proposed response. |
