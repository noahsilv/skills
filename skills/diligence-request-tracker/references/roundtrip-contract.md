# Roundtrip contract, version 1

All JSON is UTF-8, with no duplicate keys or nonfinite numbers. Text fields are
limited to 20,000 characters and input files to 8 MiB. IDs use letters, digits,
`.`, `_`, `:` or `-`, begin with a letter/digit and are at most 80 characters.
Unknown JSON fields are rejected. Paths are local filesystem paths.

## Request input and internal state

`init` and `add` read an array of complete request objects:

```json
[
  {
    "request_id": "REQ-010",
    "category": "Operating performance",
    "request": "Provide the annual revenue reconciliation for FY2025.",
    "due_date": "2026-02-20",
    "response": "",
    "evidence_reference": "",
    "status": "open",
    "private_note": "Synthetic internal reviewer note."
  }
]
```

Due date is an ISO date or an empty string. New requests must be open with empty
response/evidence fields. IDs are chosen once and never reused. Internal status is
`open`, `answered` or `closed`; no client column controls it directly.

The internal tracker contains `schema_version`, `tracker_id`, `revision`,
`parent_sha256`, `issued_ids`, `requests` and `history`. `issued_ids` retains all
request IDs, including closed requests. An add event lists new IDs. A response
review event records base, return and proposal hashes, the review, and each
accepted change's before/after values. Prior snapshots retain the complete prior
state. The helper does not delete requests.

## Client projection and manifest

The exact CSV header is:

```text
Request ID,Category,Request,Due date,Response,Evidence reference
```

The exporter quotes every cell. It inserts a protective apostrophe before
formula-like or leading-control content. The 20,000-character bound applies to
the original literal. Encoded text may exceed that bound by one character only
when it exactly matches the same request ID and column in the validated manifest.
New or edited input cannot obtain this exception by adding an apostrophe.
A separate manifest holds its schema
version, tracker ID, round ID, base SHA-256, the exact six-field rows and the CSV
SHA-256. Preserve the manifest with its base tracker snapshot. The helper requires
that every manifest row matches the source snapshot. There is no wildcard or
fuzzy matching of IDs.

Clients may reorder rows and edit only Response/Evidence reference. All rows
selected for the round must remain present once. Completely empty CSV rows are
ignored. Changes to request fields, duplicate/unknown/blank IDs and missing
expected rows are anomalies. A corrected file is a new return with its own hash;
never edit an archived original in place.

## Review input

Compute the SHA-256 of the exact proposal file with any local hash tool. A review
has exactly:

```json
{
  "review_id": "REVIEW-010",
  "actor": "Designated reviewer",
  "date": "2026-02-21",
  "reference": "Exact instruction or record authorizing these decisions",
  "proposal_sha256": "64 lowercase hexadecimal characters",
  "decisions": [
    {"request_id": "REQ-010", "accept_response": true, "close": false}
  ]
}
```

At least one decision is required. Only response IDs in the proposal may be
decided. Decisions may cover a subset; unmentioned responses stay unapplied.
`accept_response: false` records rejection without altering the request. Closing
requires both booleans to be true and some nonblank response or evidence reference.
This is explicit operator closure, not a conclusion from source verification.
References, reviewer identities and dates must be truthful in operational use;
the helper only checks their presence and structure.

Application reads the archived return by its digest-derived filename and
reconstructs the proposal. Edited proposals, changed archived inputs, a stale
tracker, anomalies or a mismatched review hash are rejected. Outputs are new
snapshots. No external application, email, client delivery or evidence download
is part of this contract.
