# Diligence request tracker

Track diligence requests across client edits and follow-up rounds using permanent IDs. Returned responses become proposals for review. The review records which responses were accepted and which requests were explicitly closed. The workflow runs locally and keeps client and internal data separate.

This self-contained implementation uses Python 3.10+ and the standard library.
It has no institutional policy fields, external systems, network calls or message
sending. The examples and reviewer records are synthetic.

## Run the example

From this package directory, use a new destination:

```sh
python examples/run_demo.py /tmp/diligence-request-demo
python -m unittest discover -s tests -v
```

The demo calls the actual CLI to create three requests with IDs `REQ-010`,
`REQ-040` and `REQ-090`, export a client CSV, archive a synthetic returned CSV,
reconcile it, and apply simulated decisions. The first request is closed only
because its review explicitly says so. The second response is accepted but its
request remains answered and open for follow-up. The third is unchanged.
Round 2 contains `REQ-040` and `REQ-090`, preserving their IDs.

Read the [first export](examples/outputs/client-round-1.csv),
[response proposal report](examples/outputs/proposals.md),
[final internal tracker](examples/outputs/tracker.json), and
[second export](examples/outputs/client-round-2.csv). Only the client CSV is
intended for client delivery; internal JSON files and reports can contain private
notes and historical responses. No files are transmitted by these commands.

## Commands

Prefix with `python scripts/tracker.py`:

| Command | Result |
|---|---|
| `init --tracker-id ID --input REQUESTS --out TRACKER` | Initial open requests with caller-assigned IDs |
| `add --tracker FILE --input REQUESTS --out NEXT` | Append requests without reusing any issued ID |
| `export --tracker FILE --round-id ID --out CSV --manifest JSON [--open-only]` | Separate client projection and internal round manifest |
| `reconcile --tracker FILE --manifest FILE --returned CSV --archive DIR --out JSON --report MD` | Original archive, anomalies and response proposals |
| `apply --tracker FILE --proposal FILE --archive DIR --review FILE --out NEXT` | New tracker snapshot after explicit review |
| `validate --tracker FILE` | Structural validity and status counts |

Exit 0 means the operation completed; exit 1 means reconciliation completed with
anomalies that block application; exit 2 means rejected input or an execution
error. Every output path must be new. A partially completed two-file export or
report can leave its first output if the second write fails; inspect the error,
retain that artifact as appropriate, and rerun with fresh paths. The tool does
not overwrite outputs during recovery.

## Boundaries and safeguards

The CSV has exactly six columns: Request ID, Category, Request, Due date,
Response, Evidence reference. Private notes and internal status are excluded by
an explicit field allowlist. Values beginning with spreadsheet formula leaders
(`=`, `+`, `-`, `@`), including after whitespace or invisible formatting
characters, and values beginning with control characters receive a leading
apostrophe. Every cell is CSV-quoted. Incoming response strings remain literal
data and are protected again on later export.

CSV readers differ. The package tests encoded bytes, not every spreadsheet
application. Keep protective prefixes intact, inspect the target application,
and use a text import setting if needed. An untouched exported response maps back
to its original literal value; the helper never strips arbitrary leading
apostrophes from a newly typed response. A valid 20,000-character literal may
occupy 20,001 characters after encoding. That extra character is accepted only
for an exact match to the same request ID and column in the export manifest;
new or edited input remains subject to the 20,000-character literal limit.

Returns must have the original headers and exact request IDs. Duplicate IDs
quarantine every matching row. Missing/blank/unknown IDs, altered request wording,
due dates or categories, extra columns, malformed CSV and parsing failures all
produce anomalies. The entire return remains unapplied until those issues are
resolved. A deliberately omitted closed request belongs in a fresh `--open-only`
round, not in a shortened return to a different manifest.

The original input bytes are saved before JSON/CSV parsing under their SHA-256.
An oversized input above 8 MiB is rejected before archival; retain it separately
and prepare a bounded copy. Cells are limited to 20,000 characters. An existing
archive entry must match the bytes exactly. Repeated reconciliation adds no
duplicate archived file, although each requested report must have a new path.

Application reconstructs the proposal from archived bytes and the embedded export
manifest, checks base and proposal hashes, and preserves all issued IDs, private
notes, prior snapshots and before/after response values. Accepting a response
sets `answered` unless explicit closure was recorded. Empty accepted responses
remain open. Request wording cannot be changed through a client return.

Hashes are not signatures, reviews are not authenticated, and manual modification
of an entire JSON history is outside this helper's protections. The helper does
not lock other applications, merge competing tracker branches, verify source
document contents, open evidence links, judge response adequacy or perform legal,
credit or investment diligence. A stale export must be reconciled against its
original snapshot before a human resolves any later competing changes.

The bundled tests cover deterministic behavior and CLI failure paths. Native
spreadsheet interoperability, agent trigger behavior and comparative model
performance are separate checks. See [the contract](references/roundtrip-contract.md)
for exact JSON and CSV fields.
