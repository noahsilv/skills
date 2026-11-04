# Prompt optimizer

Clarify a prompt without changing the task. This instruction-only skill separates the desired result from the evidence, available tools, model controls and completion checks.

For authorized use, copy this entire folder into your agent's skill directory, or attach `SKILL.md` and its referenced material in a chat. The host decides whether and how skills are loaded.

**Example request**

> Improve this prompt for a tool-using agent: Compare the two supplied sales files. Keep currency and period labels, cite the rows used, and report missing inputs. Do not run the comparison yet.

**Example optimized prompt**

> Compare the two supplied sales files using their stated currencies and periods. Cite the source rows for each reported difference. Identify missing inputs explicitly rather than treating them as zero, and flag incompatible units or periods before comparing them. Return the comparison and its supporting references. Use only the supplied files and the tools actually available.

No API calls, external accounts or Python packages are needed. The repository evaluation cases exercise intent and capability boundaries. They do not establish performance across providers or prove that every rewrite improves task accuracy.
