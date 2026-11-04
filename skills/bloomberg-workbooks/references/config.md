# BDP matrix input contract

The JSON object has exactly six keys:

| Key | Contract |
| --- | --- |
| `title` | Nonempty literal text, at most 200 characters. |
| `reference_date` | Valid calendar date in `YYYY-MM-DD` form. It is a reference date, not evidence of quote freshness. |
| `fixture` | Boolean. True labels the workbook as a synthetic fixture; false still requires evidence review. |
| `function` | Exactly `BDP` or `_xll.BDP`, copied from the intended add-in syntax. |
| `securities` | One to 500 records with `label`, `identifier` and `evidence`. Identifiers must be unique. |
| `fields` | One to 100 records with `label`, `mnemonic`, `unit` and `evidence`. Mnemonics must be unique. |

Text must be trimmed and single-line. Control characters, invalid Unicode and leading formula-sign characters are rejected. Evidence strings may contain up to 500 characters; other strings allow 200. Field mnemonics allow uppercase letters, digits and underscores, start with a letter and have at most 80 characters.

Evidence is a caller-supplied statement, not a verified source. The helper does not validate security identities, identifier checksums, field meaning, quote side or entitlement. Include the needed conventions in field labels and evidence, and review them before live use.

The sheets are Controls, Securities, Fields and Live. Each Live cell uses referenced identifier and field cells. Values use General formatting so the helper does not turn a percent-point return into a fractional percentage or silently convert units. No override arguments are generated. The confirmed refresh timestamp stays blank.

JSON is limited to 1 MB. Duplicate keys and nonfinite values are rejected. CLI validation errors return code 2 without creating an output directory; existing destinations are refused. A later filesystem failure can leave a partial directory, so inspect the success result before using files.
