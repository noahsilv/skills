# Financial data retrieval

A public-data workflow for financial analysis. The executable example retrieves one annual country indicator through the World Bank Indicators API v2. It checks the response scope and pagination, keeps provenance on each row, and distinguishes missing values from zero.

The [synthetic example](examples/README.md) spans four years across two observation pages. One value is zero, one is positive, one is null and one year is omitted. The output preserves all four cases and flags the unit as caller-supplied because the fixture's metadata unit is blank.

Read [SKILL.md](SKILL.md) for the workflow and [the contract](references/contract.md) for fields and limits. Python 3.11+ is sufficient; no API key or third-party package is required. Offline fixture mode is the reproducible demonstration. Live mode is an optional transport and was not run for this example.

Tests cover scope mismatch, incomplete pages, duplicate periods, changing pagination metadata, numeric precision, provider errors and output protection. This package does not fetch Bloomberg, Capital IQ, FRED, IMF or Data360 data. It does not discover indicators automatically or interpret methodology for the user.

[License](LICENSE): all rights reserved.
