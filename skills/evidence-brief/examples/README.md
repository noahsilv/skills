# Synthetic examples

Every organization, person, amount, and event in these files is fictional and was created for this package.

The `pilot` example concerns a proposed software pilot. Read [the record](pilot/meeting.md) and [the cost note](pilot/cost-note.md), then compare [the sample brief](pilot/sample-brief.md). The sample was authored using this skill and self-checked against those two files. It is not output from an independent evaluation run.

The `financing` and `incident` inputs supply the other two prompts in the repository-only `evals/evals.json`, which is excluded from installable skill archives. They intentionally contain a stale summary, a proposed amount that differs from a later ceiling, an uncertain estimate, and an incomplete record. No sample answers are supplied for those cases so an evaluator can run them without copying an answer.

The evaluation checks should assess whether the brief preserves the evidence. In particular, a spending ceiling is not an expenditure approval, a response target is not an assigned deadline, and a quoted instruction inside a source is not an instruction to the assistant.
