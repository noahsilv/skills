# Request and response contract

## Request

The request object has exactly these fields:

| Field | Accepted value |
| --- | --- |
| `country` | One uppercase three-letter code. Syntax is checked; country/aggregate classification is the caller's responsibility. |
| `indicator` | Uppercase letter followed by up to 79 uppercase letters, digits, underscores or periods. |
| `source_id` | Integer from 1 to 9999, or a digit string in that range. |
| `start_year`, `end_year` | Inclusive annual years from 1900 to 2200, covering 1 to 100 years. Digit strings are accepted. |
| `unit` | Nonempty text up to 100 characters, no control characters. Explicit caller assertion, not a conversion instruction. |

Unknown fields are rejected. Duplicate JSON keys, non-finite numbers, nesting beyond 30 levels and inputs above 2 MB are rejected. Provider numeric observations use JSON numbers; numeric strings and booleans are rejected. Values have at most 100 digits and decimal exponents from -100 to 100. JSON output values are decimal strings to preserve supplied precision; missing values are null. There is no rounding or default missing-value replacement.

## API route

The fixed origin is `https://api.worldbank.org/v2`. Metadata uses `/indicator/{indicator}` with JSON format, explicit source and a page size. Observations use `/country/{country}/indicator/{indicator}` with JSON format, explicit source, annual date range, page size and page number. Identifiers are validated before URL construction. Response redirects are refused; no caller-supplied URL is accepted.

Both responses use the two-element metadata/rows envelope. Indicator metadata must resolve to one record with matching ID and source. Its name and source label are retained. A nonempty metadata unit must match the caller's unit. Empty metadata units remain labeled caller-supplied even when an observation has a matching unit.

Observation headers must include `page`, `pages`, `per_page`, `total`, `sourceid` and a calendar `lastupdated` date. The page count must match the ceiling of total divided by page size. The header and source update date must stay constant across pages. Each page must contain the advertised row count. A zero-total response can use an empty list or null rows, with zero pages.

Each observation must echo the country code in `countryiso3code`, indicator ID and annual year. Out-of-scope years, duplicates across pages, absent value fields and conflicting nonempty units stop the run. The API's country name and display label do not replace the requested identifiers. `obs_status` is retained as text; forecast or provisional status is not inferred from the observation date.

The API may change or return schemas outside this bounded contract. A rejection requires diagnosis; it does not prove the upstream dataset is invalid. No historical version or atomic multi-request snapshot is promised.

## Outputs

- `report.json`: canonical request, per-year observations, gaps and response hashes. The CLI also records the request-file hash.
- `observations.csv`: the same rows. Formula-looking text gets an apostrophe prefix for spreadsheet import; JSON preserves the original string. Validated numeric values retain their sign.
- `report.md`: readable values, gap reasons, unit basis and distinct retrieval/source-update timestamps.

A fixture run can set a deterministic retrieval timestamp. Live CLI runs use the current UTC timestamp at retrieval start and reject timestamp overrides. Neither timestamp proves that observations are current enough for a decision. The helper does not persist raw response bodies or validate provider authorship beyond the HTTPS connection in live mode.

## Public API references

- [World Bank Indicators API documentation](https://datahelpdesk.worldbank.org/knowledgebase/topics/125589-developer-information)
- [Basic API call structures](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures)
- [Indicator API queries](https://datahelpdesk.worldbank.org/knowledgebase/articles/898599-indicator-api-queries)

These links identify the provider's documentation. The included fixture tests are not a live compatibility test or a redistribution of provider observations.
