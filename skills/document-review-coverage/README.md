# Document review coverage

Keep reviewer records tied to the text and review inventory they cover. The portable workflow and independently implemented Python helper inventory content blocks and reconcile unit/check pairs. They retain comments and proposed changes, and flag changed scope, stale files and missing quote spans.

## Run the example

Follow the [example guide](examples/README.md) to compare complete records, missing checks and a review tied to an earlier document. The complete case still has an unresolved revision. Reducing the checklist changes the scope and invalidates the earlier records.

To run the tests, use Python 3.11 or newer from this package directory. The helper uses the standard library.

```sh
python -m unittest discover -s tests -v
```

## Interpret coverage

Read [the workflow](SKILL.md) for the review steps and [the record format](references/record-format.md) for the JSON contract. The author developed this edition from document review and reviewer-response workflows, using independently written instructions, code and synthetic examples.

The implementation is deliberately bounded: UTF-8 Markdown/plain text only, no network access, and no source edits. It checks exact quotations and current bytes, not whether a proposal follows from the evidence, whether a comment is adequately answered, or whether a change has been implemented. A mechanically complete report can still contain open work and wrong reviewer judgments.
