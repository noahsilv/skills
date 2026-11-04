# Contributing

Keep each skill independently understandable. Place required instructions in `SKILL.md`, implementation under `scripts/`, and synthetic examples and tests beside it. Explain unsupported cases and fail explicitly when they occur.

For a proposed change:

1. Describe the user-visible problem and the intended behavior.
2. Use synthetic data. Do not submit real client files, credentials, confidential examples, personal identifiers or undisclosed external links.
3. Add a test that demonstrates the relevant failure or boundary condition.
4. Run `python scripts/validate.py` and `python scripts/test.py` from the repository root.
5. If instructions change, exercise representative prompts and record the actual output. Static text checks are not a behavioral evaluation.

A source change invalidates the existing release manifest. Maintainers regenerate it only after reviewing the complete change and its results. Tests are not a substitute for that review.

Please open an issue before contributing code while reuse/contribution terms remain restricted by the current license. Do not submit material you lack permission to share.
