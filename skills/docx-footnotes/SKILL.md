---
name: docx-footnotes
description: Add native footnotes to a supported Word .docx using explicit text markers, while preserving existing notes and writing a new file. Use for automated citations or supplementary notes when the document can be prepared with standalone marker runs and structural checks are required.
compatibility: Python 3.11 or later; standard library only. Transitional .docx files with UTF-8 XML. A Word-capable editor is needed for final visual validation.
---

# Native Word footnotes

Insert real Word footnote references and entries into a new document copy. The helper creates missing footnote parts and relationships, allocates unused IDs, and checks that ordinary notes and body references correspond one-to-one. It never updates the input or replaces an existing output.

## Prepare the edit

Read the user's document and citation requirements. Confirm the exact claim each note supports; the helper does not verify the truth or relevance of citation text. Preserve source wording unless changes are requested.

Work on a copy. Place each marker, such as `[[fn:source-one]]`, in a **standalone text run** in the main document. Each marker must occur exactly once. Markers split across runs or mixed with other text are rejected; do not flatten a formatted document to work around that error. Resolve revisions in the owning editor first, or explain that the document is unsupported.

Prepare a JSON array with exactly `marker` and `text` for each note. Note order in JSON is irrelevant: new IDs are allocated in document order, above all existing IDs. Existing IDs and separator entries retain their meaning. IDs are identifiers; this helper does not promise any displayed numbering or page layout before rendering.

```json
[
  {"marker": "[[fn:source-one]]", "text": "Synthetic source, Example report, 2030, page 4."}
]
```

## Run

From this skill's directory:

```sh
python scripts/add_footnotes.py input.docx annotated.docx --notes notes.json
```

Exit `0` means the supported structural edit succeeded; JSON reports the count, marker-to-ID mapping and `visual_validation: NOT_RUN`. If removal of the temporary hard link fails after publication, success also includes a `TEMPORARY_CLEANUP_FAILED` warning with the leftover path; remove that extra link after inspecting the output. Exit `1` means this operation published no new output. A pre-existing destination remains intact. The destination directory must exist and support hard links so a complete file can be published atomically without replacing another file.

## Verify and deliver

1. Confirm the reported marker count equals the requested note count, and address any cleanup warning. Inspect the correspondence between claims and notes.
2. Open the new file in the intended Word-compatible editor. Check for repair prompts, visible marker/entry correspondence, existing notes, numbering, page breaks and note formatting. A PDF rendering from a different editor is useful evidence of that renderer only.
3. Report structural success and actual rendering evidence separately. If Word is unavailable, deliver as structurally checked with visual validation explicitly pending; do not claim broad Word compatibility or visual fidelity.

The helper uses superscript reference runs and 10-point note text with the document's inherited font. It does not create or require named styles. Adjust visual styling in the editor if needed.

## Scope and limits

- Supports conventional Transitional `.docx`, UTF-8 XML, and plain-text notes. Main-document markers may be in ordinary body or table paragraphs.
- Rejects Strict OOXML, macros, signed packages, tracked revisions or enabled tracking, malformed or dangling footnotes, ambiguous markers, markers in text boxes/content controls/alternate content, and marker paragraphs containing complex fields.
- No rich footnote text, clickable links, cross-references, endnotes, numbering-policy edits or merge of different sources. It does not edit headers, footers or existing note text.
- Archive size, expansion, member-count and XML complexity limits are deliberate; see [implementation notes](references/implementation.md).
- Other package content—including authorship metadata, comments, attachments and external links—is retained. This tool is **not a sanitizer**. Do a separate content review before sharing a document.

For a synthetic end-to-end example and test instructions, read [README.md](README.md).
