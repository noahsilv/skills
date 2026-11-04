# Formula-plan contract

The root object has exactly `title`, `fixture`, `queries` and `outputs`. Both lists contain one to 100 records. Fixture is a boolean. Title and ordinary metadata strings are trimmed, single-line, nonempty text up to 300 characters.

Each query has:

| Key | Meaning |
| --- | --- |
| `id` | Unique query label, at most 50 characters. |
| `sheet` | Valid Excel sheet name, at most 31 characters. Outputs is reserved. Names differing only in case are rejected. |
| `anchor` | Uppercase A1 address without dollar signs. |
| `output_range` | One cell or a top-left-to-bottom-right rectangle within Excel bounds. |
| `formula` | Complete trusted provider formula, retained byte-for-byte as text. Maximum 8,192 characters. |
| `syntax_source` | Caller-supplied evidence description, at most 1,000 characters. |
| `syntax_status` | `synthetic_fixture` when fixture is true; otherwise `addin_generated` or `observed_control`. Neither promotes the output plan to a verified refresh. |
| `parameters` | Up to 100 objects, each with `cell` and `value`. Values are literal text up to 1,000 characters; formula-sign prefixes are rejected. |

Supported outer function names are SPG, SPGRANGEV, SPGTable, SPGScreen, CIQ, CIQRANGE and CIQRANGEV. Optional `@`, `_xll.` and `SNL.Clients.Office.Excel.Functions.` prefixes are preserved. The helper checks the enclosing call and quotes, including escaped apostrophes in sheet references. It does not parse or validate the arguments, referenced cells, nested expressions or provider semantics. It does not construct SPGLabel parameter rows or infer data-set numbers.

Query result rectangles on the same sheet cannot overlap. Assigned parameter cells and other query anchors cannot enter a result rectangle. A query's own anchor may be the top-left cell of its return range or sit outside it. Declare the full expected result shape; undeclared expansion is outside the check.

Every output has exactly `cell`, `query_id`, `source_cell`, `label`, `unit`, `period`, `currency` and `quote_side`. Use an explicit not-applicable label where needed. Each source must fall inside its declared query result range. Output destinations must be unique. The plan writes a quoted-sheet formula linking the Outputs cell to that source, plus metadata for the authoring tool to display. The helper does not author the display itself.

Input JSON is limited to 1 MB. Duplicate keys, invalid Unicode and nonfinite numbers are rejected. The CLI returns 2 for invalid input or an unavailable output path and refuses to overwrite an existing file. Filesystem failures during a write can leave a partial output; check success before consuming it.
