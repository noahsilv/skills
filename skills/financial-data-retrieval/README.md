# Financial data retrieval

A public-data workflow for financial analysis. The executable example retrieves one annual country indicator through the World Bank Indicators API v2. It checks the response scope and pagination, keeps provenance on each row, and distinguishes missing values from zero.

## Run the offline example

Follow the [example commands](examples/README.md) from the package directory with Python 3.11 or newer. The fixture spans four years across two observation pages and runs without an API key or third-party packages. The optional live mode was not used for this example.

## Read the observations

Compare the four rows of the [saved report](examples/output/report.md). One observation is zero, one is positive, one is explicitly null and one year is absent from the provider response. The report distinguishes all four. It labels the unit as caller-supplied because the fixture's metadata leaves it blank.

## Coverage

Read [the workflow](SKILL.md) for the retrieval steps and [the contract](references/contract.md) for required fields and limits.

Tests cover scope mismatch, incomplete pages, duplicate periods, changing pagination metadata, numeric precision, provider errors and output protection. This package does not fetch Bloomberg, Capital IQ, FRED, IMF or Data360 data. It does not discover indicators automatically or interpret methodology for the user.

[License](LICENSE): all rights reserved.
