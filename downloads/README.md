# Finance skill downloads

Each `.skill` archive contains the source files of one public package, including its instructions, examples, license and tests. The worked examples use synthetic data. Use is subject to the [repository license](../LICENSE).

| Finance task | Download | Read the worked example |
| --- | --- | --- |
| Analyze historical financial statements and check six accounting reconciliations | [Financial statement analysis](financial-statement-analysis.skill) | [Statement checks and metrics](../skills/financial-statement-analysis/examples/README.md) |
| Plan an update from reported actuals to a forecast model | [Actuals update planner](actuals-update-planner.skill) | [Period, scale and sign mapping](../skills/actuals-update-planner/examples/README.md) |
| Calculate the dated cash payments on a fixed-rate facility | [Debt schedule](debt-schedule.skill) | [Draws, principal and interest](../skills/debt-schedule/examples/README.md) |
| Stress operating assumptions and compare debt service coverage | [Scenario analysis](scenario-analysis.skill) | [Operating case and debt handoff](../skills/scenario-analysis/examples/README.md) |
| Compare refinancing with capital spending at closing | [Financing pro forma](financing-pro-forma.skill) | [Uses of proceeds and closing balances](../skills/financing-pro-forma/README.md) |

## Inspect a package

Open the archive with a ZIP reader. Start with the package README for the financial question and example command. `SKILL.md` gives the agent workflow. Use a new directory outside the repository for any example outputs you retain. The core scenario calculation runs independently. Its optional connected example also needs the debt schedule package.

## Verify a download

The [release manifest](../release-manifest.json) lists the SHA-256 digest and size of each archive. From a checkout with the development requirements installed, run the following commands.

```sh
python scripts/validate.py --manifest
python scripts/test_downloads.py
```

The first command compares every archive member with its corresponding public source file. The skill packager leaves two authoring files in the repository, the [actuals review prompts](../skills/actuals-update-planner/evals/evals.json) and [statement analysis prompts](../skills/financial-statement-analysis/evals/evals.json). The executable tests ship with all five packages.

The second command extracts each verified package into its own temporary directory and runs its tests there. Some tests require a filesystem with link support.

The [harnesses](../harnesses/README.md) run across packages from a repository checkout. Their guides show the inputs, commands and evidence for each financial review.
