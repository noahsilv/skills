# Evidence brief

Write a short decision brief from mixed source material, with explicit attribution, decision status and unresolved evidence. This portable workflow uses the language model to assess what each source supports. Finding a citation string alone is insufficient.

Read [SKILL.md](SKILL.md), then inspect the [synthetic examples](examples/README.md). No external services or Python dependencies are required. Three realistic behavior prompts are in the repository-only `evals/evals.json`; they cover both financing and software delivery decisions. That folder is excluded from installable skill archives. Evaluation results should be recorded separately after actual runs. The checked-in example is an authored demonstration, not a benchmark result.

This package was independently written from the author's experience developing source-grounded meeting and management briefing workflows. This portable edition contains no private transcripts, counterpart examples, organizational templates, filing destinations, or approval rules.

The skill does not authenticate its sources, settle disputed evidence, approve decisions, or send messages. A source may be wrong, incomplete, or outdated. Citation lookup alone cannot validate a paraphrase or detect an omitted qualification; that review remains a reasoning task.
