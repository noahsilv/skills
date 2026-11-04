# Synthetic artifact gate result

Verdict: **ATTESTED** — one required check has a current self-reported pass.

| Required check | Reported result | Evidence bound by the gate |
| --- | --- | --- |
| csv-shape | pass | sample.csv, checker.py, result.log, the run manifest, and the check record |

The synthetic checker confirms an `account,amount` header, two columns per
data row, and at least one data row. It does not validate amounts, accounting,
formulas, or external data. `scripts/demo.py` produces the exact run UUID,
current file fingerprints, and readable/JSON reports in a fresh directory.

Changing `sample.csv` after initialization causes rejection. Changing a log or
checker after recording also causes rejection. Omitting the record yields
`INCOMPLETE`; the gate does not infer success from the absence of failures.

All check results remain self-reported attestations. Hashes establish identity
of the observed bytes. The gate neither independently executes checkers nor
certifies artifact correctness or recalculation.
