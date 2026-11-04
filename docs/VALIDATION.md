# Validation and limitations

## Reproduce the executable checks

From the repository root, create a fresh Python 3.11 environment and install `requirements-dev.txt`. Run:

```sh
python scripts/validate.py --manifest
python scripts/test.py
```

The metadata check also parses source files, resolves local Markdown links and compares the release manifest with the working tree. The test runner executes four independent package test suites; zero available suites is a failure. Prompt behavior is evaluated separately.

Fixtures are constructed from synthetic JSON, small generated spreadsheets and minimal Office XML. Test-generated Office files are temporary and are not shipped in the repository. The executable suites exercise:

| Package | Checks |
| --- | --- |
| Workbook tieout | Explicit coverage, unit conversion, missing or incorrect data, tolerance boundaries, typed comparisons and formula-cache limitations. |
| Model regression testing | Changed/unchanged declarations, missing watch items, period/unit/type changes, decimal precision, baseline preservation and read-only spreadsheet export. |
| Office package audit | Input bounds, ZIP/XML errors, relationship/content-type consistency, review surfaces, report redaction and exit statuses. |
| DOCX footnotes | Existing and newly created note infrastructure, IDs, markers, XML namespaces, package preservation, unsupported inputs and output non-overwrite guarantees. |

## Release check results

On 2026-11-04, the local Python 3.11 validation run used a fresh environment with only the declared dependencies. All **107 executable tests passed**: 30 for footnotes, 20 for regression testing/export, 40 for package audit and 17 for workbook tieout. Package frontmatter validation passed for all five skills. Independently generated malformed-input probes were used to find and fix edge cases before this run.

These are local results, not a claim that a remote CI run or native Office validation has completed. The commands above let a reader reproduce the checks against the manifest.

## Prompt behavior

[Recorded prompt evaluations](PROMPT_EVALUATIONS.md) contain the actual outputs for three synthetic tasks. A separate evaluation agent reviewed 11 output-based assertions. This is a single-run smoke evaluation in a Codex agent environment. It is not a statistical benchmark, a measurement of speed, or evidence of performance on other models or hosts.

## Limits that matter

- Spreadsheet helpers read supplied snapshots or stored workbook values. They do not execute Excel or recalculate formulas. Cached formula values remain review-required.
- A consistent comparison does not establish that a source is accurate, that the selected watch list is complete, or that a financial assumption is appropriate.
- Office inspection implements selected package checks, not every OOXML schema rule. Arbitrary XML, images, embedded objects and other content may require separate substantive review.
- The Word editor has a deliberately narrow supported scope. A structural test cannot establish pagination, appearance, accessibility or native application compatibility.
- Microsoft Word, Excel and PowerPoint opening/rendering, spreadsheet-engine recalculation, and automatic skill triggering in every agent host were **not run** in this environment. Use the intended applications to validate artifacts before operational delivery.
- Automated scans and synthetic tests do not establish confidentiality or authorship. Review the actual material and the intended use.

The manifest binds the published source to the reviewed files. It is a reproducibility aid, not a digital signature or a third-party certification. Updating a source file invalidates its recorded hash.
