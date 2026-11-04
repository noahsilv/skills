# Synthetic annual series

All identifiers and observations in this fixture are invented. `ZZZ` and `DEMO.ANNUAL.RATE` are deliberately unsuitable as live provider identifiers. The fixture follows the supported response shape; it is not a downloaded World Bank dataset.

From the package directory:

```sh
python scripts/retrieve.py examples/request.json --fixtures examples/fixtures --retrieved-at 2026-11-04T00:00:00Z --out /tmp/indicator-example
```

The saved [report](output/report.md), [JSON](output/report.json) and [CSV](output/observations.csv) were generated with that command into a fresh directory and copied here.

| Period | Observation | Expected result |
| --- | --- | --- |
| 2021 | Numeric zero on page 2 | Preserve zero. |
| 2022 | No provider row | Gap: provider omitted requested year. |
| 2023 | Explicit null on page 1 | Gap: provider returned null. |
| 2024 | Numeric 3.25 on page 1 | Preserve 3.25. |

The report counts three requests: indicator metadata and two observation pages. The metadata unit is blank, so `percent` remains an explicit caller assertion. Retrieval time is fixed for reproducibility; the source-update date is a different synthetic date. Changing either fixture page counter or source update date causes a rejection rather than a partial table.

Live mode was not used. A real request requires verified country, indicator, source and units; do not change the fixture's mode label to imply a provider download.
