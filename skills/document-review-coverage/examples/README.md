# Synthetic review examples

All example text and reviewer records were created for this package. They do not describe a real organization, project, customer, or review.

[draft.md](draft.md) overstates approval of a component rollout. [supporting-note.md](supporting-note.md) describes a conditional proposal. The generated [inventory](inventory.json) contains four text blocks and two declared review checks, for eight expected unit/check pairs. The original draft is never changed by the helper.

| Case | Input ledger/artifact | Actual helper result | What remains |
| --- | --- | --- | --- |
| Complete records | [reviews-complete.json](reviews-complete.json) | 8 of 8 valid unique pairs; exit 0 | Record 6 proposes correcting approval to a conditional proposal; record 8 contains a reply awaiting acceptance. |
| Incomplete records | [reviews-incomplete.json](reviews-incomplete.json) | 6 of 8 valid unique pairs; exit 2 | One pair is absent; record 6 cites text that does not exist in the evidence. Its proposal remains visible but does not count. |
| Stale artifact | [draft-stale.md](draft-stale.md) with the complete ledger | Binding and coverage unverified; exit 2 | The rollout date changed. No old record is counted against the new bytes. |
| Missing scope coverage | [reviews-clarity-only.json](reviews-clarity-only.json) with the original inventory | 4 of 8 valid unique pairs; exit 2 | Source-support review records are missing. |
| Reduced check list | [inventory-scope-changed.json](inventory-scope-changed.json) with the unchanged clarity-only ledger | Inventory binding and coverage unverified; exit 2 | Removing source-support from the inventory changes its hash. No unchanged ledger record counts toward the reduced scope. |

Inspect the actual [complete report](outputs/complete/report.md), [incomplete report](outputs/incomplete/report.md), [stale-artifact report](outputs/stale/report.md), [missing-scope report](outputs/scope-original/report.md), and [changed-scope report](outputs/scope-changed/report.md). These files were produced by the helper, not written as hoped-for output. Every report labels the semantic conclusion `NOT_ASSESSED`.

Run from the skill directory with fresh output paths:

```sh
python scripts/review_coverage.py inventory examples/draft.md \
  --checks clarity source-support --out /tmp/review-demo-inventory.json

python scripts/review_coverage.py reconcile examples/draft.md \
  examples/inventory.json examples/reviews-complete.json \
  --out-dir /tmp/review-demo-complete

python scripts/review_coverage.py reconcile examples/draft.md \
  examples/inventory.json examples/reviews-incomplete.json \
  --out-dir /tmp/review-demo-incomplete

python scripts/review_coverage.py reconcile examples/draft-stale.md \
  examples/inventory.json examples/reviews-complete.json \
  --out-dir /tmp/review-demo-stale

python scripts/review_coverage.py reconcile examples/draft.md \
  examples/inventory.json examples/reviews-clarity-only.json \
  --out-dir /tmp/review-demo-scope-original

python scripts/review_coverage.py reconcile examples/draft.md \
  examples/inventory-scope-changed.json examples/reviews-clarity-only.json \
  --out-dir /tmp/review-demo-scope-changed
```

All reconciliation commands except the complete-records case intentionally exit 2 while still writing their reports. Choose new paths when running again: existing files or report directories are refused. Evidence paths are relative to the ledger, so the supplied ledgers resolve `supporting-note.md` without machine-specific paths. Every ledger records the exact hash of the original `inventory.json`; the changed-scope inventory deliberately fails that binding.

The complete example is a record-coverage demonstration, not an endorsement of every reviewer assessment. In particular, the `clarity` row for the incorrect approval sentence does not establish factual correctness; the separate `source-support` row proposes correcting it. A test also deliberately supplies a semantically unrelated revision with a matching support quote and verifies that the helper leaves judgment `NOT_ASSESSED`.
