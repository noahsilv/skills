# Annual indicator retrieval

Mode: **synthetic-fixture**. Status: **COMPLETE_WITH_GAPS**.

Synthetic-fixture mode contains invented observations and does not contact the provider.

Indicator: DEMO.ANNUAL.RATE. Invented annual funding rate.
Requests: 3. Provider rows: 3. Gaps: 2.

| Country | Period | Value | Unit | Gap |
| --- | --- | --- | --- | --- |
| ZZZ | 2021 | 0 | percent |  |
| ZZZ | 2022 |  | percent | provider omitted requested year |
| ZZZ | 2023 |  | percent | provider returned null |
| ZZZ | 2024 | 3.25 | percent |  |

Unit basis: caller-supplied; provider metadata unit is blank.
Retrieved at: 2026-11-04T00:00:00Z. Source last updated: 2026-01-15.

The JSON records request URLs and response hashes. Retrieval time is separate from the source update date.
Missing observations are not zero. No interpolation, currency conversion or revision history is inferred.
