# Evidence brief

A portable workflow for converting mixed source material into a short decision brief with explicit attribution, decision status, and unresolved evidence. It shows the language-model part of an evidence workflow: deciding what a source actually supports, rather than merely finding a citation string.

Read [SKILL.md](SKILL.md), then inspect the [synthetic examples](examples/README.md). No external services or Python dependencies are required. Three realistic behavior prompts are in the repository-only `evals/evals.json`; they cover both financing and software delivery decisions. That folder is excluded from installable skill archives. Evaluation results should be recorded separately after actual runs. The checked-in example is an authored demonstration, not a benchmark result.

This package was independently written from the author's experience developing source-grounded meeting and management briefing workflows. This portable edition contains no private transcripts, counterpart examples, organizational templates, filing destinations, or approval rules.

The skill does not authenticate its sources, settle disputed evidence, approve decisions, or send messages. A source may be wrong, incomplete, or outdated. Citation lookup alone cannot validate a paraphrase or detect an omitted qualification; that review remains a reasoning task.
