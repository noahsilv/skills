---
name: office-package-audit
description: Inspect an Office document, spreadsheet or presentation for broken package relationships, malformed XML, duplicate identifiers and content that needs review before sharing. Use after scripted Office edits or when checking metadata, hidden content, comments, revisions, notes, embedded objects or external links. Produces a read-only JSON report with part locations and explicit inspection limits.
compatibility: Python 3.10 or newer; standard library only. Does not require or launch Office. Supports modern Office Open XML formats, not legacy binary Office files or PDFs.
---

# Office package audit

Find structural defects and review surfaces in the file the user actually intends to deliver. This audit does not decide confidentiality, identify AI authorship, sanitize a file, recalculate formulas or certify that Office will open it without repair.

## Run the inspection

Use the supplied file path. Confirm which version is intended if several plausible deliverables exist. Run from this skill directory, or use the script's absolute path:

```sh
python scripts/audit.py path/to/document.docx > audit.json
```

The script reads a bounded snapshot and never changes the input, extracts members, follows links or runs embedded code. Its SHA-256 identifies the bytes inspected. Keep the report private when package filenames or member names are sensitive; those names and locations appear in the report even though document text, metadata values and external target URLs do not.

Read `exit_code` and `status` as well as the findings:

| Exit | Meaning | Next action |
|---|---|---|
| 0 | Implemented checks passed; no listed review surface was found | Continue the content and application checks required for the deliverable |
| 1 | Review needed; no implemented structural error was found | Inspect every indicated surface and any uninspected parts |
| 2 | Input unsupported, unreadable, over limits or structurally invalid | Resolve the named cause and rerun on the actual resulting file |

Do not describe exit 0 as confidential-data clearance or native application validation. If preflight fails, no package members were inspected. A failed XML parse or an opaque member remains in `coverage.uninspected_parts`. Files above the documented limits need a separately bounded review method; do not silently raise limits or report them as clean.

## Review the findings

1. For structural errors, locate the member and XML location reported. Inspect the source document and repair through a suitable authoring tool in a separate working copy. The auditor does not propose a destructive automatic fix.
2. For metadata, comments, revisions, notes, hidden items, custom XML and supplemental data, inspect the actual content locally. Check why it is present and whether it belongs in the intended deliverable. Deleting visible text can leave other representations behind.
3. For external relationships, establish whether the dependency is intentional and appropriate. The script has not opened the target. Do not follow it merely because it appears in a source file.
4. For binary or other uninspected parts, use a suitable viewer or domain tool. Images can contain readable text; embedded files can contain their own metadata and content. Macro-enabled input is not executed or certified safe.
5. After any edits, rerun the audit on the saved deliverable and record its new hash. Review the changed content and check native application behavior where that matters. A clean XML parse is not a successful render, a fresh formula calculation or a clean desktop Office open.

## Report

State the inspected file/hash, status, structural errors, unresolved review items, uninspected content and checks still required. Use source locations rather than reproducing sensitive excerpts. Separate an observed defect from a possibility that needs review. If a reviewer could not inspect a required part, leave it unresolved.

See [README.md](README.md) for supported formats, limits and commands. The [synthetic examples](examples/make_examples.py) and [tests](tests/test_audit.py) illustrate behavior without distributing real Office documents.
