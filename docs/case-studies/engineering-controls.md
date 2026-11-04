# Routing and quality controls

Two recurring automation mistakes are choosing a workflow whose tools are unavailable and relying on a check that applies to an older file. This demonstration makes both conditions visible.

## Executed results

The router receives an explicit workbook-tieout request against the portfolio catalog. With only Python declared, it retains the requested skill and reports the missing openpyxl dependency. With both declared, it reports the declared capabilities as available. Neither result runs the skill or proves that a tool works.

The artifact demonstration runs a small, known CSV-shape checker, captures its log, and binds the checker, artifact and result to one run. Aggregation initially returns **ATTESTED**. After the synthetic CSV changes, the same evidence returns an **INCOMPLETE** error and creates no new report.

[Read the executed summary](outputs/engineering-controls.md).

## Reproduce

From the repository root, choose a new destination:

```sh
python examples/engineering_controls_demo.py /tmp/engineering-controls-example
```

The destination contains the routing results, actual checker log, run/record fingerprints and stale-file error. No external service is called. The deliberately changed file is a newly created synthetic fixture.

## Design decisions

- Routing is bounded and explainable; lexical matching is not presented as semantic certainty.
- Capabilities are explicit caller declarations, not inferred permissions.
- Check records bind to exact artifacts and run bytes; prior success does not carry forward after edits.
- ATTESTED means self-reported evidence is complete and consistent. Hashes do not authenticate a reviewer or prove that a calculation is correct.
- Unsupported recalculation remains unverified rather than being inferred from a log message.

Inspect [skill-router](../../skills/skill-router/README.md) and [artifact-quality-gate](../../skills/artifact-quality-gate/README.md) for contracts and tests. The [Office audit](../../skills/office-package-audit/README.md) and [footnote editor](../../skills/docx-footnotes/README.md) provide additional examples of bounded file tooling and explicit unsupported cases.
