# Synthetic evidence exercise

`inputs/source-initial.txt` reports 18.5 million USD of FY2025 revenue for
Synthetic Asset A. `inputs/source-revised.txt` reports 19.1 million USD for the
same context without explaining the change. Both extracts omit outstanding debt.
The two JSON updates record exact source hashes and line locators.

The demo records a simulated acceptance of the first revenue claim, then leaves
the revision and debt gap pending. The readable output contains one accepted
claim, two pending claims, one unresolved difference and one unknown. No source
truth is asserted, and the conflicting claim never silently replaces the first.

Run `python examples/run_demo.py NEW_DIRECTORY` from the package root. The runner
uses `scripts/ledger.py` through subprocess calls, checks source fingerprints,
and produces complete review-bound snapshots. `outputs/` holds an actual run's
JSON and Markdown artifacts. The source text remains under `inputs/`.

All names, dates, values and review records are invented for this exercise. The
simulated acceptance is a test fixture, not a real review or approval.
