# Mapping and source contract

Run [the synthetic generator](../examples/make_demo.py) to obtain a complete mapping, a simple model and a two-page source-text example. Financial numbers in JSON are strings, never binary floats. Duplicate keys, IDs, model rows, source files and prior columns are rejected, as are unknown schema keys. Each source and mapped model is bound to its SHA-256 snapshot.

## Top-level mapping

| Field | Required content |
|---|---|
| `schema_version` | Integer `1`. |
| `entity`, `scope` | Exact entity text; scope `consolidated` or `standalone`. |
| `model_sha256`, `sheet` | Current XLSX digest and the model sheet name. |
| `model_context` | `entity_cell`, `scope_cell`, `unit_cell`, `unit_label`; all cells must match their declared literal text. Unit label is exactly currency plus `units`, `thousands`, `millions` or `billions`, such as `USD millions`, consistent with target scale. |
| `label_column`, `header_row` | Current labels and period-header positions. |
| `target` | `column`, `expected_header`, `actual_header`, `period`, `currency`, `scale`. |
| `source_sheet` | Proposed new sheet; 1–31 ASCII letters, digits, spaces, underscores or hyphens. An existing case-insensitive match is rejected. |
| `forecast_columns` | Nonempty array of `column`, `expected_header`; each lies after the target. Every existing cell outside the proposed edits is protected, including unlisted future columns. |
| `sources` | Nonempty source register described below. |
| `mappings` | Nonempty monetary-input mappings described below. |
| `excluded_rows` | Array of `row`, `label`, `reason`. Empty is valid. Use for assumptions or unrelated fields; missing reported actuals block the plan. |

A period object has exactly `start`, `end`, inclusive ISO dates; at most 372 days. Currency is a declared three-letter uppercase code and must agree between model and source. Scale is one of the strings `"1"`, `"1000"`, `"1000000"`, `"1000000000"`. No FX conversion is supported.

Source objects have exactly `id`, `file`, `sha256`, `entity`, `scope`, `currency`, `scale`, `period`, `audit_status`, `context_evidence`, `audit_evidence`. `file` is a `.txt` basename immediately within the source directory; symlinks and directory traversal are rejected. Sources are UTF-8, limited to 5 MB each; form feeds (`\f`) separate physical pages. Each source filename is unique.

Both evidence objects have `page` (positive integer) and `excerpt` (nonempty literal text, with whitespace normalized for matching). Context evidence must explicitly contain entity, scope, currency, start and end dates as complete tokens, plus an explicit numeric declaration such as `scale 1000;` (a whitespace, semicolon or end-of-excerpt follows the number). This prevents scale `1` from accidentally matching `1000` or a date digit. Audit evidence must include the word matching `audit_status`: `audited`, `unaudited` or `interim`. This constrained input requires reviewed, page-preserving source text with explicit context; if that information is not supported in the supplied evidence, the helper cannot validate the source. Do not invent a quotation or alter source text merely to make it pass.

These are checks on declared metadata and text, not document authentication, accounting-policy interpretation or opinion verification. Retain original documents separately and review their content.

## Per-input mapping

Each mapping contains exactly these fields:

```json
{
  "id": "sales",
  "row": 5,
  "label": "Revenue",
  "expected_estimate": "330",
  "source_id": "half_year",
  "source_label": "Revenue",
  "source_value": "675000",
  "reported_as": "675,000",
  "citation": {"page": 2, "excerpt": "Revenue 675,000"},
  "kind": "flow",
  "basis": "cumulative",
  "sign_multiplier": 1,
  "prior_periods": [
    {
      "column": "B",
      "expected_header": "Q1 2025A",
      "period": {"start": "2025-01-01", "end": "2025-03-31"},
      "expected_value": "300"
    }
  ]
}
```

For a USD-thousands source and USD-millions model, conversion factor is `1000 / 1000000 × 1 = 0.001`. A half-year source amount of `675000` becomes `675` millions; deducting the first-quarter `300` produces standalone Q2 actuals of `375`, and a variance of `45` against the estimate `330`.

`reported_as` allows ordinary numerals, comma groups and parentheses for negatives. Its complete numeric token must immediately follow `source_label` in the cited excerpt, separated by whitespace and optionally a colon or pipe. This bounded reader supports label/amount text rows; selecting a non-first amount from a comparative table requires a different reviewed extraction workflow. Its parsed signed value must equal `source_value`. Decimal strings permit at most 24 integer and 12 fractional digits. `sign_multiplier` is exactly integer `1` or `-1`; the factor is computed rather than accepted as an arbitrary override.

`kind` is `flow` or `stock`, and both are monetary amounts only. Standalone flows need matching source/target start and end dates, with empty `prior_periods`. Stocks need the matching end date and empty prior periods; only standalone stock basis is permitted. A cumulative flow needs a source starting before the target, the same end date, and prior periods that exactly partition from source start to the day before target start. Prior cells must be numeric hardcodes with matching header and expected value. They share the model scale/sign; their historical source accuracy is outside this helper's evidence check.

No ratios, EPS, share counts, average prices or percentages are derived by subtraction. No formula cell is an input target or prior deduction, even if a cached value exists. Headers, context and row labels must be literal text; formula-generated labels are unsupported. Every mapped row label and estimate must match the current workbook. Every target-column numeric hardcode below the header must have a mapping or explicit exclusion. All formulas on every inspected sheet are recorded as protected, and none can overlap a proposed edit.

## Output and boundaries

`plan.json` includes typed proposed source cells (`text`, `number`, `formula`), original estimate snapshots, proposed model links and header edit, prospective actual amounts, variances and evidence. Source-sheet formula rows express conversion and prior-period deductions. These formula strings are instructions only; no spreadsheet engine has executed them. The `plan.md` report provides the review table and source citations.

Decimal arithmetic uses precision 80; variance percentages are rounded to six decimal places using half-even rounding. Percentage = `(actual − estimate) / abs(estimate) × 100`. A zero estimate returns a null percentage and `ZERO_ESTIMATE`; a loss/negative estimate is allowed. Positive variance is a signed difference, not a judgment of favorability.

XLSX numeric hardcodes are read through openpyxl's numeric representation and converted with `Decimal(str(value))`; this cannot recover precision already lost in Excel or prior saves. The explicit expected-value check catches disagreement with the prepared map. Numeric strings and booleans in workbook input cells are rejected.

The bounded reader accepts `.xlsx` only, up to 25 MB compressed and 100 MB expanded. Inspection is capped at 10,000 rows and 200 columns per sheet and 250,000 cells overall. It inspects actual worksheet XML coordinates before relying on cached dimensions, rejecting hidden out-of-bounds cells, duplicate rows/cells, mismatched cell-row coordinates and duplicate package members. The map is capped at 5 MB, 100 sources and 1,000 mappings. Ordinary identifiers are 1–80 ASCII identifier characters, and text fields are nonempty plain text with at most 2,000 characters. No macros, charts, pivots, formatting, external-link calculations or broad workbook preservation guarantee is needed because the helper never saves a workbook.

The model, map and each source are re-read before report delivery to detect input changes. Reports require a new directory, including refusal to follow an existing output symlink. The saved hashes identify the plan's snapshot; recheck them immediately before any later application.
