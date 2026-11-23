# Prompt optimizer

Clarify a prompt without changing the task. This instruction-only skill separates the desired result from the evidence, available tools, model controls and completion checks.

For authorized use, copy this entire folder into your agent's skill directory, or attach `SKILL.md` and its referenced material in a chat. The host decides whether and how skills are loaded.

## Example request

> Improve this prompt for a tool-using agent: Compare the two supplied sales files. Keep currency and period labels, cite the rows used, and report missing inputs. Do not run the comparison yet.

## Revised prompt

> Compare the two supplied sales files using their stated currencies and periods. Cite the source rows for each reported difference. Identify missing inputs explicitly rather than treating them as zero, and flag incompatible units or periods before comparing them. Return the comparison and its supporting references. Use only the supplied files and the tools actually available.

## Requirements and evaluation

The workflow requires no API calls, external accounts or Python packages. The [evaluation cases](evals/evals.json) check whether a rewrite preserves the request and respects the tools available to the agent. Performance across providers and changes in task accuracy require separate evaluation.
