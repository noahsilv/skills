# Synthetic routing result

The request names **sheet inspection** and asks for report/evidence review.

| Rank | Skill | Match | Missing declared capability |
| --- | --- | --- | --- |
| 1 | table-inspector | Named alias: sheet inspection | office-engine |
| 2 | claim-review | Lexical overlap with claims, evidence, report, review, against | None |

Three catalog entries have a match; one is omitted by `limit: 2`. The named
skill remains first even though it has a dependency gap. JSON output also
contains the exact matched token list and a SHA-256 for each selected file.
Run `scripts/demo.py --output-dir NEW_EXTERNAL_DIRECTORY` to materialize the
synthetic catalog and save results with current hashes.

These are deterministic suggestions. Capabilities are caller declarations and
no skill or tool has been executed.
