# Validation and limitations

## Portfolio validation

The November 5, 2026 working-tree update passed **522 tests across 18 executable
packages** on Python 3.12. Four existing JSON loaders now enforce a 100-level
nesting limit explicitly rather than relying on interpreter recursion behavior.
The router retains v1 behavior and adds caller-reviewed intent/exclusion handling.
The new context composition demo executed the ledger, exact synthetic fixture
checker and artifact gate, including missing-check and changed-source failures.

Three paired old/new evidence-brief tasks were generated in separate contexts and
graded against their original sources: **15/15 assertions for each version**.
One sample per case and a non-blinded model reviewer establish no quality advantage.
Token usage, timing and cost were unavailable. This update was tested from source;
the prior archive-validation statement below applies to the preceding edition,
not newly packaged archives. No publication or installation is implied.

This 20-skill edition expands the original five-skill portfolio. The results below describe the reviewed source and packaged demonstrations.

The preceding edition passed **518 executable tests across 18 packages** using Python 3.11 and the declared dependencies. Tests exercise financial definitions, exact numeric handling, source/mapping coverage, request roundtrips, stale-file evidence, routing, document review coverage and Office structure. Those same 518 tests passed from fresh extracted packages, and all 20 archives were checked against that edition's source files. Synthetic case-study commands were also executed; their reports are linked from the README.

The evidence-brief skill passed **15 source-based assertions across three actual tasks** in a separate reviewer pass. The same three baseline tasks without the skill passed 14; the observed miss strengthened a conditional statement into a commitment. One sample per case cannot establish general performance superiority. The unchanged prompt optimizer retains its earlier 11 checks across three cases, documented in [its evaluation record](PROMPT_EVALUATIONS.md).

The five data and integration additions have 164 executable tests within that total. Bloomberg tests cover BDP construction and blank caches; Capital IQ tests cover formula preservation and declared layouts. The audit tests recompute mapped financial results. Data-retrieval tests use synthetic responses. MCP tests cover the bounded protocol and API adapter.

The MCP example also passed a subprocess stdio/loopback HTTP demonstration and an interoperability check with the official MCP Python SDK 1.29.0. Those local checks were reproduced independently. They do not establish live-provider access or hosted deployment. The optional SDK check uses the package-local requirements file and is separate from the standard-library unit suite.

Five additional response-only scenarios checked provider and integration limits. Both the with-skill and baseline responses passed all 18 assertions. These ties provide no evidence of a performance advantage; the exercise checks the stated boundaries and does not test live systems.

## Reproduce

From the repository root, install requirements-dev.txt in a fresh Python 3.11 environment and run:

```sh
python scripts/build_catalog.py --check
python scripts/validate.py --manifest
python scripts/test.py
```

Each package has its own instructions, synthetic examples and limits. The runner rejects absent or zero-test executable suites. Instruction-only workflows require behavioral review as well as static validation.

## Scope

Calculations and checks are bounded by explicit input contracts. A consistent source citation, matching hash or complete review record does not establish financial truth, reviewer authority or the adequacy of the chosen scope. Proposed actuals edits are plans; cached spreadsheet values are not recalculation. Routing suggestions do not execute tools.

Native Word/Excel/PowerPoint rendering, live-provider refresh, spreadsheet-engine recalculation, deployment-scale reliability and automatic triggering across agent hosts have not been tested here. Office tools do not certify universal format compatibility or confidentiality. No operational time-saving, adoption or financial-impact measurements are claimed.

The manifest identifies the reviewed source bytes and excludes itself from its hashes. It is not a signature, external certification or evidence of publication.
