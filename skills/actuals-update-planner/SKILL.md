---
name: actuals-update-planner
description: Plan a source-linked actuals update to an existing forecast workbook using explicit row, period, unit and evidence mappings. Use when reported annual or interim results must replace estimate inputs while preserving forecast assumptions and formulas. Produces proposed cell edits, estimate snapshots and variances; reads XLSX but never changes or recalculates it.
compatibility: Python 3.11+ and openpyxl 3.1.5; XLSX input, explicit JSON mapping and page-preserving UTF-8 source text.
---

# Actuals update planner

Turn a reviewed financial disclosure into an inspectable update plan. Separate the decisions that identify the right model period and source from the arithmetic that checks them. The helper always stops at a plan, including for a simple workbook.

## Map the model and source

1. Read the current workbook and original financial report. Identify entity, consolidation scope, reporting units, estimate column, source period and the reporting vintage. Read the audit report or interim review status. Do not treat the presence of an audit label as proof of authenticity or a clean opinion.
2. Map rows by their current labels and structure. Record current entity/scope/unit cell contents, estimate and forward headers, numerical estimate values, and the workbook SHA-256. Formula rows stay protected. A source item with an uncertain row, period, scope or definition prevents the dependent edit; settle the ambiguity first.
3. Prepare page-preserving UTF-8 text from the source. One form-feed character separates physical pages; a text file without form feeds has exactly one page. Verify material transcriptions against the original report. Record the text-file SHA-256, physical page, exact excerpt, printed number, source label, context evidence and audit-status evidence. The helper checks excerpts against these text files; it does not parse PDFs or verify the text against a PDF.
4. Follow [the mapping contract](references/schema.md). Explicitly distinguish standalone flows, cumulative flows and period-end stocks. Convert currency scale and sign only; this helper excludes FX, ratios, per-share data and weighted averages. Cumulative deductions require prior hardcodes that partition the earlier coverage without a gap or overlap. Stocks cannot be derived by subtracting earlier balances.
5. Account for every numeric hardcode below the header in the target column: map it, or explicitly exclude an assumption/other field with its label and reason. A missing reported actual is a blocker, not a reason to relabel an estimate as an assumption. Forward drivers stay unchanged. The planner does not reforecast.

## Generate and review

From this package directory:

```sh
python examples/make_demo.py --out /tmp/actuals-planner-demo --case annual
python scripts/plan.py /tmp/actuals-planner-demo/model.xlsx --mapping /tmp/actuals-planner-demo/mapping.json --sources /tmp/actuals-planner-demo/sources --out /tmp/actuals-planner-review
```

Use new output directories. Exit 0 means `PLAN_READY`: declared mappings, source excerpts, amounts, periods and file snapshots passed the bounded checks. It does not mean the workbook was updated, recalculated, audited or approved. Exit 2 means `REJECTED`; inspect the named input problem. No partial plan is delivered for a rejected mapping.

Review `plan.md` and `plan.json`. The JSON enumerates every proposed typed source-sheet cell, every replacement link and the period-header change. It snapshots the original estimate, records source conversion and prior-period deductions, lists existing protected formulas, and shows source-linked absolute and percentage variances. The percentage is `(actual − estimate) / abs(estimate) × 100`; a zero estimate gives an undefined percentage. Positive variances are not automatically favorable.

## Deliver the plan

Name the period, entity, units, audit-status declaration, mapped/excluded counts, source hashes and open review items. State that all workbook application, recalculation and effects on formula rows remain pending. Do not present input variances as post-update results for calculated EBITDA, earnings, margins or forecasts.

If a separate authorized workflow applies the plan, recheck hashes and target values before edits, use an appropriate spreadsheet application on a copy, recalculate, and verify the source links, period label, protected formulas and forecast inputs against the plan. Reconcile the resulting workbook to the source. This package does not perform that write or post-update verification.

## Examples and tests

[The examples](examples/README.md) include annual results and a cumulative half-year disclosure feeding a standalone second quarter. Run:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

These deterministic tests validate the helper and protection behavior on synthetic files. No production outcome or agent-triggering benchmark is claimed.
