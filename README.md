# Practical agent skills

A curated portfolio by [Noah Silverman](https://github.com/noahsilv): five skills for working with evidence, spreadsheets, documents and prompts. Each has a bounded purpose, explicit limitations and examples that can be reproduced without private data or internal systems.

| Skill | What it demonstrates |
| --- | --- |
| [Prompt optimizer](skills/prompt-optimizer/SKILL.md) | Preserve intent while turning a request into a testable agent brief. |
| [Workbook tieout](skills/workbook-tieout/SKILL.md) | Reconcile explicitly mapped spreadsheet cells and report coverage and calculation limitations. |
| [Model regression testing](skills/model-regression-testing/SKILL.md) | Distinguish expected changes from regressions without silently replacing the baseline. |
| [Office package audit](skills/office-package-audit/SKILL.md) | Inspect document structure, hidden content and embedded dependencies without guessing authorship. |
| [DOCX footnotes](skills/docx-footnotes/SKILL.md) | Add native footnotes within a deliberately bounded Word-processing format. |

The work combines workflow design, small executable tools, defensive input handling and evidence-based checks. Implementation and review were assisted by AI. This is a portfolio of concrete methods, not a claim that an agent or a passing test can replace professional judgment.

## Use a skill

For authorized use, copy an entire folder from `skills/` into the skill directory supported by your agent. Read its `SKILL.md` first. Some hosts load skill metadata automatically; others require attaching the instructions and relevant references. Installation does not grant file access, tools or permissions. These instructions document the mechanics and do not expand the reuse rights stated in the license.

The Python tools can also be used directly. From the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/validate.py
python scripts/test.py
```

Python 3.11 or newer is the supported development baseline. Package READMEs describe individual commands and dependencies. Tests generate synthetic files in temporary directories; no Office application or account is required for the automated checks.

## What the checks establish

The tools report the evidence they inspected. Spreadsheet caches are not recalculation, package structure is not visual rendering, and a marker in a document cannot establish who authored it. Read [validation and limitations](docs/VALIDATION.md) before relying on a result. The [recorded prompt examples](docs/PROMPT_EVALUATIONS.md) show actual evaluated outputs.

The committed [release manifest](release-manifest.json) records the reviewed source files and their hashes. It excludes itself to avoid a circular hash. Run `python scripts/validate.py --manifest` to check that the working files match it.

## Contributing and rights

See [CONTRIBUTING.md](CONTRIBUTING.md) for the validation workflow and [LICENSE](LICENSE) for reuse terms. Examples are synthetic and demonstrate mechanics; they are not investment, credit or legal recommendations.
