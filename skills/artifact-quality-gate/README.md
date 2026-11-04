# Artifact Quality Gate

This local draft records the requested checks and the files used for each reported result. It aggregates the evidence only while those files still match. Requires Python 3.11+ and the standard library.

The strongest successful verdict is **ATTESTED**: every required check has a
self-reported pass, the files still match, and the records belong to the same
run. This is not independent checker execution, proof of correctness, or a
calculation-engine certification.

## Synthetic demonstration

From this package directory, use a destination that does not yet exist:

```bash
python scripts/demo.py --output-dir /tmp/artifact-gate-demo
python -m unittest discover -s tests -v
```

The demo copies synthetic CSV data and a small checker into a new directory,
runs that known checker once, saves its log, and builds a run, record, JSON
report, and readable `report.md`. The checker only validates CSV shape. The
gate itself never executes checkers or interprets log contents. The demo shows
how a caller supplies evidence; it does not upgrade the gate's assurance.

[examples/output.md](examples/output.md) explains the example result. The
three `gate.py` commands below can also reproduce the lifecycle manually.
`--root` must identify the same absolute directory throughout a run.

## 1. Initialize explicitly requested checks

```json
{
  "schema_version": 1,
  "artifacts": [{"id": "sample-data", "path": "sample.csv"}],
  "checks": [{
    "id": "csv-shape",
    "artifact_ids": ["sample-data"],
    "requirement": "Check the CSV header, row widths, and presence of data rows.",
    "kind": "file_check"
  }]
}
```

```bash
python scripts/gate.py init --root /tmp/my-check-root --spec /tmp/spec.json --output /tmp/run.json
```

The root and files must already exist. Both lists need 1–1,000 entries.
Artifact IDs and check IDs are unique lowercase kebab strings (at most 100
characters). Each check references one or more unique artifact IDs; every
artifact must be covered. Requirements are nonempty text, at most 10,000
characters. `kind` is `file_check` or `recalculation`. There is no implicit
default checklist and no pass for zero checks.

The generated run has exactly `schema_version`, `run_id` (UUID4), `created_at`
(UTC ISO 8601), `root` (absolute), `artifacts`, and `checks`. Each artifact gains
`sha256` and `size`. The checks are frozen as supplied. Keep the exact JSON
bytes: records bind to the run file hash, so even reformatting the run after
recording invalidates the association. New artifacts or requirements need a
new run. The UTC timestamp records initialization time, not proof of when a
checker ran.

## 2. Record a reported result

Run the actual check through a separately authorized workflow, then supply:

```json
{
  "schema_version": 1,
  "check_id": "csv-shape",
  "status": "pass",
  "summary": "Caller reports that the CSV header and row widths matched.",
  "evidence": [
    {"role": "checker", "path": "checker.py"},
    {"role": "log", "path": "result.log"}
  ]
}
```

```bash
python scripts/gate.py record --root /tmp/my-check-root --run /tmp/run.json --request /tmp/record-request.json --output /tmp/check-record.json
```

`check_id` must have been required at initialization. `status` is exactly
`pass`, `fail`, or `not_run`. `summary` is nonempty text, at most 10,000
characters. Evidence is a list of at most 100 files with role `checker`, `log`,
or `supporting`. A checker file may be source code or a stable written review
procedure; fingerprinting it does not prove its execution. Both pass and fail
need separate checker and log files. `not_run` may have an empty evidence list
and needs an honest explanation in its summary.

Evidence paths must differ from the inspected artifacts and from each other,
including hard links. A record contains exactly `schema_version`, `run_id`,
`run_sha256`, `check_id`, `status`, `summary`, `artifacts`, `evidence`, and
`assurance: "self_reported"`. Artifacts match the initialized snapshots;
evidence entries gain `sha256` and `size`. The gate rechecks all initialized
artifacts before recording and does not edit the run or request.

Recalculation passes are rejected at both recording and aggregation. The
package has no calculation-engine supervision or trusted engine receipt
validator. Use `not_run` for this unsupported requirement, or `fail` for an
observed failure with evidence. Fields claiming an engine or independent
execution are not part of the accepted schema. A generic `file_check` must
not be used to claim verified recalculation.

## 3. Aggregate current evidence

```bash
python scripts/gate.py aggregate --root /tmp/my-check-root --run /tmp/run.json --record /tmp/check-record.json --output /tmp/verdict.json
```

Repeat `--record` for additional checks. The command never scans a directory
or silently picks the newest result. It rejects duplicate check records,
unrequested checks, mixed UUIDs, mismatched run bytes, changed artifact bytes,
changed logs/checkers, malformed status values, and record/artifact mismatches.

| Verdict | Meaning | Exit |
| --- | --- | --- |
| ATTESTED | All explicitly required checks have matched self-reported passes | 0 |
| FINDINGS | Required records are complete; at least one reports failure | 1 |
| INCOMPLETE | A required record is missing or reports not_run | 3 |
| INCOMPLETE error | Invalid input, stale file, unsafe path, mixed run, or write refusal | 2 |

If both a failed and a missing check exist, `INCOMPLETE` takes precedence and
the failed check remains visible. Missing/`not_run` reports are written for
review. Validation errors produce a JSON error on stderr and create no new
report. Never reuse an older report as the result of a failed aggregation.

A successful aggregate report includes run identity/hash, verdict, required
and supplied record counts, missing/not-run/failed IDs, per-check requirement
and summary, assurance limitation, and fingerprints of the supplied record
files. Keep records beside the report to inspect their artifact, checker, and
log hashes. Reporting zero missing checks is not a substitute for reviewing
whether the original required-check list was appropriate.

## JSON, path, and write rules

Every shown key is required. Unknown keys are rejected at every schema level,
as are duplicate JSON keys, nonfinite numbers, booleans in integer fields,
malformed hashes, and wrong value types. JSON inputs must be UTF-8, at most
2 MiB. Human text fields have no surrounding whitespace or control characters.
`schema_version` is integer 1. A SHA-256 has 64 lowercase hexadecimal characters
and a byte size is a nonnegative integer.

Artifact and evidence paths are POSIX paths relative to the run root. No
absolute paths, drive prefixes, backslashes, empty components, `.`/`..`, or
symlinks are accepted. Root, inputs, and output parent paths may not contain
symlinks. Files must be regular files; duplicate paths or hard-link aliases
within the relevant list are rejected. Existing files are never overwritten,
including an output path pointing to an input. Output parent directories must
already exist. Source artifacts and request/run/evidence inputs remain intact.

## Assurance boundary and testing

This is a local evidence consistency gate, not a signature service or security
boundary. An author who can rewrite manifests and records can fabricate a
consistent set; a matching checker/log hash does not prove a check happened.
It does not check log truthfulness, coverage quality, financial accuracy,
provider refresh, cached-value freshness, or semantic adequacy of requirements.
The record creator must report those facts honestly, and the reviewer must
assess the evidence. Reusing old but unchanged logs cannot be detected from
hashes alone. Recalculation remains unsupported even if a log claims success.

The filesystem is assumed to be a trusted local workspace with no adversarial
concurrent renames. The implementation rejects observed symlinks and changes
during hashing; it is not a transaction across files or a hardened sandbox.
Aggregate again after any potential change and create a fresh run after edits.

Tests exercise valid, failed, missing and not-run records, same-name artifact
changes, changed logs/checkers, cross-run evidence, malformed JSON/status/types,
unsupported recalculation, duplicate and escaped paths, symlinks/hard links,
CLI exit codes, and refusal to overwrite. `evals/evals.json` provides realistic
review prompts; no comparative model-performance score is claimed.

## Rights

See [LICENSE](LICENSE). Public portfolio visibility does not grant general
permission to copy, modify, distribute, or commercially reuse this package.
