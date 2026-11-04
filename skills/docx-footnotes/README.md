# docx-footnotes

A small, dependency-free workflow for inserting native Word footnotes into a new document copy. It can create a missing footnotes part, preserve existing notes, and reject edits it cannot safely represent.

The implementation is independently authored for this public collection. It uses published WordprocessingML structures; no document template or example from a working project is included.

## Try a synthetic example

Python 3.11 or later is required. Run from this directory, using new output paths:

```sh
python examples/make_example.py example.docx
python scripts/add_footnotes.py example.docx annotated.docx --notes examples/notes.json
```

The expected result is `STRUCTURALLY_CHECKED`, with two inserted notes and `visual_validation: NOT_RUN`. The generator fails if `example.docx` already exists. The editor also refuses to replace an existing `annotated.docx`.

Open `annotated.docx` in your intended editor to inspect marker/footnote correspondence and layout. This repository's checks exercise package structure, preservation and error handling. They are not Microsoft Word rendering certification.

## Test

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_*.py' -v
```

Tests cover missing infrastructure, existing IDs and separators, document order, XML escaping, relationship namespaces, custom part paths, unrelated-part preservation, non-overwrite guarantees, repeat operations, malformed references, revisions and bounded archive/XML handling. Fixtures are generated in temporary directories.

## Input and output

The notes file is an array of `{ "marker": "[[fn:identifier]]", "text": "Plain citation text." }`. The marker must occupy a complete text run in the main document. Word can split visually continuous text into multiple XML runs; inspect or regenerate the marker run if the helper rejects it.

The script returns a JSON status and the new marker-to-ID mapping. It prints no note contents. XML edits preserve namespace declarations, including prefixes mentioned by markup-compatibility attributes. New reference subtrees bind their prefix locally, and the serialized XML is reparsed before its references are checked. Unchanged ZIP members retain their bytes and per-member metadata; the archive itself is rewritten.

The new output is published by a hard link from a complete temporary archive on the same filesystem. If hard links are unavailable, the operation fails rather than weakening the non-overwrite guarantee. Cleanup is attempted after success and failure. If cleanup fails after publication, the command still reports successful insertion and includes a `TEMPORARY_CLEANUP_FAILED` warning with the leftover temporary path. Remove the extra link after checking the output. If cleanup fails during an unsuccessful operation, the error JSON includes the leftover-path warning.

Read [SKILL.md](SKILL.md) for agent instructions and [implementation notes](references/implementation.md) for supported scope and design references.
