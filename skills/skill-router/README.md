# Skill Router

Local draft portfolio package. Route an explicit request against an explicit
catalog without dispatching tools or importing skill code. Python 3.11+;
standard library only. All example names and content are synthetic.

## Run the example

From this package directory, choose a destination that does not yet exist:

```bash
python scripts/demo.py --output-dir /tmp/skill-router-demo
python scripts/route.py --catalog /tmp/skill-router-demo/catalog.json --root /tmp/skill-router-demo/catalog-root --request /tmp/skill-router-demo/request.json
python -m unittest discover -s tests -v
```

The demo materializes `examples/templates/*.txt` as synthetic `SKILL.md` files
only in the new external directory. It copies the sample catalog and request,
then saves `result.json` and readable `result.md`. It rejects destinations inside
this package and refuses to reuse existing directories. The packaged skill
contains only its own top-level `SKILL.md`; the fixture skill trees are created
at runtime so they cannot be mistaken for nested installable skills.

Use `--output /tmp/new-route.json` to write a new result file. Output paths may
not already exist. A catalog-wide validation failure returns exit 2 and a JSON
error on stderr; a valid result, including no matches, returns exit 0.

## Catalog contract

```json
{
  "schema_version": 1,
  "skills": [
    {
      "id": "sample-review",
      "path": "sample-review/SKILL.md",
      "description": "Check report claims against a supplied evidence list.",
      "aliases": ["claim review"],
      "required_capabilities": ["python3.11"]
    }
  ]
}
```

All shown keys are required and no other keys are accepted. The catalog must
contain 1–1,000 entries. IDs use lowercase kebab case. Aliases use ASCII letters,
digits, spaces, underscores, and hyphens, starting with a letter or digit.
Case and separators normalize to token sequences: `Claim-Review` and
`claim_review` collide. A normalized name or alias must occur exactly once
across the catalog; omit aliases equivalent to an ID, including the same skill's
ID. This rejects ambiguous routing rather than picking an arbitrary owner.

Paths use `/`, are relative to `--root`, and end in `SKILL.md`. Every path must
exist as a regular file. Absolute paths, drive prefixes, empty components,
`.`/`..`, backslashes, symlink components, duplicate paths, and hard links to a
second catalog entry are rejected. The root must be an existing directory and
its path must have no symlink components.

Descriptions are nonempty strings with no control characters or surrounding
whitespace. Aliases and capabilities have at most 100 entries each and each
entry is at most 100 characters. Capabilities use lowercase letters, digits,
hyphens, and dots, for example `python3.11` or `office-engine`.

## Request contract

```json
{
  "schema_version": 1,
  "query": "Use claim review on this report",
  "available_capabilities": ["python3.11"],
  "limit": 3
}
```

The four keys are required. `schema_version` is integer 1, not a boolean or
float. `limit` is an integer from 1 to 5. Query length is 1–10,000 characters.
Available capabilities are exact declarations; aliases for capabilities are
not inferred. Both JSON files must be UTF-8 and at most 2 MiB. Duplicate JSON
keys, nonfinite numbers, unknown keys, and wrong types are rejected.

## Ranking and output

1. Normalize the query to ASCII letter/digit tokens.
2. Identify full ID or alias token sequences in the query. Sort named matches
   ahead of all remaining candidates, then by the longest matching name in
   tokens, then by lexical overlap, then by ID.
3. For remaining entries, count distinct query tokens shared with ID, aliases,
   or description after a small documented stopword set is removed. Ignore
   entries with zero overlap. Ties sort by ID, independent of catalog order.
4. Return at most `limit` suggestions with `candidate_count` and `omitted_count`.

Each suggestion records `id`, `path`, `match_kind` (`named` or `lexical`),
`matched_names`, `matched_terms`, `lexical_overlap`, `missing_capabilities`,
`capability_status`, and `skill_sha256`. A missing capability does not erase a
named request; it remains visible as a gap. `declared_available` means all
required capability strings were supplied by the caller, not that tools were
tested. The example's readable result is [examples/output.md](examples/output.md).

## Limits and engineering choices

This is an explainable lexical baseline, not a semantic classifier. It does not
infer synonyms, handle negation, assess instruction quality, or prove that a
suggestion is appropriate. Quoted and negated aliases still match. A hash
identifies file bytes and says nothing about correctness or safety. The script
never executes discovered skills, imports their Python, traverses companions,
opens connectors, or dispatches agents. A caller reviews selected instructions
under its own task and policy before proceeding.

The filesystem checks assume a trusted local workspace with no adversarial
concurrent renames. They reject observed symlinks and detect changes while
hashing, but are not a hardened sandbox or transaction across multiple files.
Run again after catalog or skill edits. The CLI reads its inputs and exclusively
creates an optional output; it never updates catalogs or source skills.

Tests cover ranking, bounds, empty matches, capability gaps, deterministic
ties, JSON/type validation, ambiguous aliases, path escape, symlinks, hard
links, stale catalog entries, and CLI input preservation. The prompts in
`evals/evals.json` are review scenarios, not claimed model-performance scores.

## Rights

See [LICENSE](LICENSE). Public portfolio visibility does not grant general
permission to copy, modify, distribute, or commercially reuse this package.
