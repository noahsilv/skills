# Validation and limitations

## Portfolio validation

This 15-skill edition expands the original five-skill portfolio. The results below describe the reviewed source and packaged demonstrations.

The current local run passed **354 executable tests across 13 packages** using Python 3.11 and the declared dependencies. Tests exercise financial definitions, exact numeric handling, source/mapping coverage, request roundtrips, stale-file evidence, routing, document review coverage and Office structure. Synthetic case-study commands were also executed; their reports are linked from the README.

The evidence-brief skill passed **15 source-based assertions across three actual tasks** in a separate reviewer pass. The same three baseline tasks without the skill passed 14; the observed miss strengthened a conditional statement into a commitment. One sample per case cannot establish general performance superiority. The unchanged prompt optimizer retains its earlier 11 checks across three cases, documented in [its evaluation record](PROMPT_EVALUATIONS.md).

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
