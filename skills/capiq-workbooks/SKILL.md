---
name: capiq-workbooks
description: Plan and review Capital IQ Excel workflows using supplied Pro SPG or legacy CIQ formulas. Use for provider-linked financials, history, security tables or screens that need formula preservation, reserved result areas and linked presentation cells. Live retrieval requires the licensed add-in.
compatibility: Python 3.11 standard library for the formula-plan helper. Licensed Capital IQ access and the corresponding Excel add-in are required for provider execution; a separate authoring route is needed for XLSX files.
---

# Capital IQ workbooks

Preserve working add-in formulas and make their output layout explicit. The helper writes a JSON plan; it does not create an Excel workbook or retrieve values.

## Inspect the data request

Identify the data set, entity or security, field, period, currency, units and quote side. Distinguish reported versus adjusted financials, actuals versus estimates and consolidated versus standalone statements. A company identifier is not automatically a security identifier.

Inspect existing formulas and caches before editing a workbook. Capital IQ Pro and legacy Capital IQ have different function families and identifier conventions. Do not translate field mnemonics or identifiers by analogy.

## Obtain the formula and layout

Use the installed Formula Builder or an authorized working workbook to obtain the complete formula. Preserve its prefixes, omitted arguments, options and parameter references. Check the provider's documentation for the selected data set. A field listing does not establish a valid argument signature or successful return.

Read [the input contract](references/config.md). Supply literal parameter cells, the query anchor and the reserved return rectangle. A scalar or native array anchor may occupy the top-left result cell. An add-in-managed table may have an anchor outside its result area. Inspect that distinction in the generated workbook; do not assume all table formulas use the same layout.

Read [the provider workflow](references/workflow.md) for function selection and refresh checks. The helper preserves trusted formula text; it is not a formula interpreter, malware scanner or security sandbox. Review formulas before submitting them to an authoring tool.

## Build and inspect a plan

```sh
python scripts/build_plan.py examples/config.json /tmp/capiq-plan.json
```

The output must not exist. Check the plan's assigned cells, declared ranges and output metadata. It rejects overlaps with declared result regions and duplicate assignments. It cannot predict undeclared result expansion or validate references inside formula arguments.

Use the plan with an appropriate spreadsheet authoring tool. Write parameter literals as text, provider formulas as formulas and Outputs cells as links to the raw return cells. Keep metadata visible beside the output. Do not insert market-data hardcodes or fabricated caches.

The bundled formula uses synthetic identifiers and arguments to test exact preservation. It is not a verified provider query. For real inputs, supply documented syntax and select the corresponding caller evidence status. The helper still reports live refresh `NOT_RUN`.

## Verify in licensed Excel

Refresh one control query, inspect its returns and save. Check all requested identifiers and fields before treating the expanded result as verified. Review periods, unit magnitude, currency, quote side and visible errors. Reopen the saved formulas and values. A query's field labels or accepted formula text do not prove that its data refreshed.

Keep errors and missing observations visible. Never replace them with zero or stale values. Only create a dated values-only snapshot after successful retrieval; retain the live formulas. Do not use a generic spreadsheet engine as evidence that provider functions ran.

Report the plan or workbook, what was checked, any missing evidence and whether live refresh and native Excel rendering were run.
