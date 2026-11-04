# Document review coverage

A portable review workflow and independently implemented Python helper that bind reviewer records to a particular text artifact and saved review inventory. It inventories content blocks, reconciles unit/check pairs, retains comments and proposed changes, and detects changed scope, stale files, and missing quote spans.

Read [SKILL.md](SKILL.md) for the workflow and [the record format](references/record-format.md) for the JSON contract. Follow [the example guide](examples/README.md) to inspect complete records with an unresolved revision, missing records, a stale document, and a reduced check list that cannot make an incomplete review complete.

Requires Python 3.11+ with no third-party packages:

```sh
python -m unittest discover -s tests -v
```

This portable edition grew from the author's document review coverage and reviewer-response ledger workflows. Its instructions, script, schema, and synthetic examples were written independently for this package. It includes no private editorial rules, institutional templates, actual comments, project data, or organizational approval mechanics.

The implementation is deliberately bounded: UTF-8 Markdown/plain text only, no network access, and no source edits. It checks exact quotations and current bytes, not whether a proposal follows from the evidence, whether a comment is adequately answered, or whether a change has been implemented. A mechanically complete report can still contain open work and wrong reviewer judgments.
