# Validation and limitations

## Finance harnesses and closing-date pro forma

| Check | Observed result |
| --- | --- |
| Annual actuals review | Two Windows runs produced the same recorded summary. The harness also passed the Linux and Windows jobs in [the public CI run](https://github.com/noahsilv/skills/actions/runs/45116620861). |
| Debt and liquidity | Five tests passed, including an independent search for the minimum retention cap across 625 four-period cash paths. See [the CI run](https://github.com/noahsilv/skills/actions/runs/45117122900). |
| Resumable credit review | Eight tests passed. They exercise changed inputs, altered outputs, concurrent writers, interruption and retry. See [the CI run](https://github.com/noahsilv/skills/actions/runs/45118211849). |
| Financing pro forma | Fourteen tests passed from source and from the extracted skill download. The extracted files matched the public package source. See [the CI run](https://github.com/noahsilv/skills/actions/runs/45119281454). |

A separate reviewer used the pro forma instructions on two new synthetic financing cases and checked the arithmetic independently. One case closed with USD150 million of cash and USD345 million of net debt. The other lacked USD48 million of funding and withheld its closing ratios. This was one forward test of the instructions.

## Earlier portfolio validation

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

From the repository root, create a virtual environment with `python -m venv .venv`. Activate it with `.\.venv\Scripts\Activate.ps1` in PowerShell or `. .venv/bin/activate` in a POSIX shell. Install the dependencies and run the checks.

```sh
python -m pip install -r requirements-dev.txt
python scripts/build_catalog.py --check
python scripts/validate.py --manifest
python scripts/test.py
python harnesses/actuals-review/run.py
python -m unittest discover -s harnesses/debt-liquidity -p "test_*.py"
python -m unittest discover -s harnesses/credit-review -p "test_*.py"
python -m unittest discover -s harnesses/financial-evidence -p "test_*.py"
python -m unittest discover -s harnesses/excel-recalculation
```

Each package has its own instructions, synthetic examples and limits. The runner rejects absent or zero-test executable suites. The full suite runs on Ubuntu in CI. Several package tests use symbolic links or hard links and need suitable filesystem permissions. The Windows CI job checks the catalog, manifest and actuals harness.

## Scope

Calculations and checks are bounded by explicit input contracts. A consistent source citation, matching hash or complete review record does not establish financial truth, reviewer authority or the adequacy of the chosen scope. Proposed actuals edits are plans; cached spreadsheet values are not recalculation. Routing suggestions do not execute tools.

The [financing workbook recalculation](../harnesses/excel-recalculation/README.md) compares the saved results of a baseline and revised workbook with a separate Python calculation. The Ubuntu workflow runs both with LibreOffice Calc. Desktop Excel opened an add-in dialog during the local test and a verified save remains outstanding. Native Office rendering, live-provider refresh, deployment-scale reliability and automatic triggering across agent hosts still require separate evidence.

The manifest identifies the reviewed source bytes and excludes itself from its hashes. It is not a signature, external certification or evidence of publication.
