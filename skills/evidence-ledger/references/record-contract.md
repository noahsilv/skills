# Record contract, version 1

Use UTF-8 JSON with no duplicate keys or nonfinite numbers. Inputs are limited to
8 MiB and individual text fields to 20,000 characters. Unknown fields are rejected
to avoid silently dropping data. IDs use letters, digits, `.`, `_`, `:` or `-`,
start with a letter/digit and are at most 80 characters. All list IDs are unique.

## Source and claim input

An update contains only `sources` and `claims` arrays. A source has exactly:

```json
{
  "source_id": "SRC-A-v1",
  "label": "Synthetic operating summary",
  "version": "2026-01-15",
  "sha256": "64 lowercase hexadecimal characters from the exact file",
  "limitations": "Synthetic illustration; no assurance work performed."
}
```

Version text describes the version; the hash identifies its bytes. Different
source bytes require a new source ID. A claim has exactly:

```json
{
  "claim_id": "CLM-010",
  "entity": "Synthetic Asset A",
  "metric": "annual_revenue",
  "period": "FY2025",
  "units": "million",
  "currency": "USD",
  "basis": "reported_actual",
  "qualifiers": ["standalone"],
  "value": 18.5,
  "evidence": [{"source_id": "SRC-A-v1", "locator": "Line 4"}],
  "unknown_reason": null
}
```

Values are strings, booleans, finite numbers or null. Every populated value needs
at least one source and a nonempty locator. Null values need a nonempty reason
and cannot be accepted. Currency is null for noncurrency metrics or a three-letter
uppercase code; the helper does not validate an official currency registry.
`basis` is an explicit operator label. Period and unit labels are not interpreted.
Qualifiers are distinct strings, preserved in their declared order.

The ledger stores `schema_version`, `ledger_id`, `revision`, `parent_sha256`,
`sources`, `claims` and `reviews`. Revision 0 has no reviews and a null parent.
Each applied review adds one revision and preserves all prior objects. The
parent digest refers to the exact previous JSON bytes, including whitespace.

## Review input

First hash the exact staged proposal using `fingerprint`. A review contains:

```json
{
  "review_id": "REVIEW-010",
  "actor": "Designated reviewer",
  "date": "2026-02-01",
  "reference": "Exact instruction or record authorizing these decisions",
  "proposal_sha256": "64 lowercase hexadecimal characters",
  "decisions": [{"claim_id": "CLM-010", "action": "accept", "supersedes": []}]
}
```

The actor, date and reference must describe a real review in operational use.
They are required text, not authenticated credentials. `action` is `accept` or
`reject`. Only pending claims can receive a decision. A rejection has no
supersession links. An acceptance must list exactly the active accepted claims
with the same entity, metric, period and basis, even if their values agree. It
cannot supersede a claim about another entity or period. This explicit rule
keeps each active target unambiguous without choosing between competing sources.

An empty decisions list records the proposal while leaving new claims pending.
To decide a previously pending claim, stage an update with empty arrays against
the current snapshot and bind the new review to that proposal. Human source
verification and the authority of a decision are outside the helper.
