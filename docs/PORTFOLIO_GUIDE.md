# A guide for hiring teams

This collection sits at the intersection of finance and AI workflow engineering. It makes recurring professional work explicit enough to inspect, automate in bounded steps and check against evidence.

## If you are reviewing financial capability

Start with the financial and diligence case studies. Look for explicit definitions of entity, period, currency, units and signs; accounting or cash-flow reconciliation; distinctions between missing data and zero; and a clear explanation of which conclusions are supported.

The debt and scenario demonstrations expose assumptions instead of embedding unexplained benchmark thresholds. The actuals workflow produces a plan that can be reviewed before a model is changed. The evidence workflow preserves uncertainty and the difference between a proposal and an accepted decision.

## If you are reviewing engineering capability

Start with routing and quality controls, then inspect a package's implementation and tests. Look for deterministic boundaries around language-model work: input schemas, identifier stability, exact numeric handling, read-only or non-overwriting output behavior, content hashes, failure states and reproducible test fixtures.

The router proposes workflows and reports capability gaps; it does not pretend that a suggestion executed a tool. A quality gate ties check evidence to a particular artifact; it does not treat a matching hash as proof that a calculation or judgment is correct. These distinctions are intentional interface design.

## How to interpret authorship and evidence

Noah Silverman's portfolio brings together workflow design and AI-assisted development and review. The repository supplies generalized implementations and synthetic demonstrations of methods from a broader personal workflow library. It should be assessed on the design choices and evidence visible here. It does not claim that every line was manually written, that a public example was deployed in a client environment, or that a measured business outcome exists where none is shown.

Tests demonstrate behavior within stated inputs and supported formats. Prompt evaluations are small behavioral exercises, not broad model benchmarks. Native Office rendering, live data-provider refresh, deployment-scale reliability and autonomous production operation require separate evidence; do not infer them from the examples.

## Suggested discussion topics

- How would a source discrepancy change the financial conclusion or the next workflow step?
- Which assumptions belong in the input contract rather than in an agent's guess?
- What should remain a judgment task, and what can be checked deterministically?
- How does the workflow detect that an output or its supporting evidence has become stale?
- Which failure modes need tests before the workflow can handle a new file type or data source?
