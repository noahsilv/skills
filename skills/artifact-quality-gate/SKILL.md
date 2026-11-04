---
name: artifact-quality-gate
description: Validate that explicitly required artifact checks have complete self-reported records bound to current file hashes and one immutable run. Use when collecting file review evidence, reconciling check logs, or preparing a delivery note that must distinguish attested checks from missing, stale, or failed checks. Rehashes artifacts, checker files, and logs; does not execute checkers, independently certify correctness, or validate recalculation.
---

# Artifact Quality Gate

Make the requested checks and their evidence reviewable. A result belongs to
one run and the exact artifact bytes that were inspected; reused filenames are
not enough to establish that relationship.

1. Identify the artifact root and the checks the user actually requested. Put
   each artifact and each required check in a spec using [README.md](README.md).
   Give every check a concrete requirement and the artifact IDs it covers.
   Every artifact needs at least one check; an empty checklist is rejected.
2. Initialize a fresh run with `python scripts/gate.py init --root ROOT
   --spec SPEC --output NEW_RUN.json`. Keep the run unchanged. It freezes a
   UUID, UTC timestamp, absolute root, artifact paths/hashes, and requirements.
3. Run or obtain each checker separately under the user's authorized workflow.
   Review what it actually inspected. Save its checker identity and result log
   inside the artifact root. Do not substitute cached results for a fresh check.
4. For each required check, prepare a record request with `pass`, `fail`, or
   `not_run`, an honest summary, and evidence paths. Both `pass` and `fail`
   require distinct checker and log files. Record it with `python scripts/gate.py
   record --root ROOT --run RUN --request REQUEST --output NEW_RECORD.json`.
5. Aggregate with `python scripts/gate.py aggregate --root ROOT --run RUN
   --record RECORD --output NEW_REPORT.json`, repeating `--record` as needed.
   The gate rehashes artifacts and evidence. Missing checks and `not_run`
   remain `INCOMPLETE`; completed failures are `FINDINGS`; all required
   self-reported passes are `ATTESTED`.
6. State the verdict, any missing or failed requirements, and the assurance
   limitation in the delivery note. Re-run aggregation immediately before use
   if artifacts or evidence may have changed. An artifact edit needs a fresh
   run and fresh checks, not new hashes pasted into old records.

Treat `ATTESTED` as completeness of matched self-reported evidence, not an
independent quality certification. The gate cannot determine whether a log is
truthful, whether a checker is adequate, or whether a requirement was omitted.
Hashes identify file bytes; they do not prove formulas, facts, or conclusions.

Use `kind: recalculation` for a calculation-engine requirement. This package
does not supervise or validate engines, so it rejects a recalculation `pass`.
Record `not_run` with the reason, or `fail` for an observed failure backed by
checker/log evidence. Do not relabel recalculation as a generic file check to
obtain `ATTESTED`.

All commands read existing inputs and create a new output exclusively.
Malformed JSON, unknown keys, unsafe paths, symlinks, mixed runs, duplicate
records, and stale files return an error with `INCOMPLETE`; no success report
is created. Use the synthetic `scripts/demo.py --output-dir NEW_DIRECTORY`
example to inspect the lifecycle, and `python -m unittest discover -s tests -v`
to test the contracts. Python 3.11+ and the standard library are sufficient.
