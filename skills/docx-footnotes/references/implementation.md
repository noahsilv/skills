# Implementation notes

The helper edits four parts at most: the main document, its relationships, content-type declarations and the footnotes part. It writes a complete new archive, retaining the byte contents of unrelated members. XML serialization of edited parts can change whitespace and attribute presentation; this is not byte-preserving XML surgery.

## Footnote identity

The body's `w:footnoteReference` points to an ordinary `w:footnote` by `w:id`. Separator entries are identified by `w:type`. For an existing part, all IDs and entries are preserved. New normal IDs are above the largest existing ID; no rule assumes that a specific positive number is reserved.

A new footnotes part starts with conventional separator IDs `-1` and `0`. Ordinary notes start at `1`. Missing infrastructure is created only when there is no conflicting unlinked footnotes part. An existing footnotes part must already have a matching relationship and content-type declaration.

The new notes use `w:footnoteRef` for the mark inside each note and `w:vertAlign` for superscript formatting. Plain-text citation content is XML-escaped by the serializer. Notes are one paragraph each; newline characters do not request a separately formatted paragraph.

IDs use ASCII digits, at most ten digits plus an optional minus sign for separator entries, within the signed 32-bit range. The bounded helper rejects longer lexical representations even if extra leading zeros would describe the same mathematical integer. New body-reference subtrees declare their `w` binding locally to avoid inheriting a shadowed namespace. Reparsed serialized output must retain the one-to-one reference check before it can be published. A newly created document relationships part receives its own content-type override when the package has no applicable default.

## Bounded input

The limits are 64 MiB source archive size, 128 MiB expanded total, 32 MiB per member, 2,048 members, and a compression ratio of at most 500 per member. XML parts are limited to depth 128 and 250,000 nodes per part. DTD/entity declarations, duplicate or noncanonical member paths, ZIP encryption and symlink entries are rejected. No members are extracted to the filesystem and no relationship targets are fetched.

These are implementation bounds, not a comprehensive malicious-document detector. Do not open an untrusted Office document merely because this helper accepted its structure.

## Deliberate exclusions

The tool does not convert Strict to Transitional OOXML, migrate tracked changes, repair broken existing notes, preserve signatures, process macros, infer AI authorship, or certify document disclosure safety. It requires conventional `word/document.xml`, a package office-document relationship, and a Word document main content type. An existing footnotes relationship may point to a different internal XML part with a canonical path.

## Public structural references

- [ECMA-376 Office Open XML](https://ecma-international.org/publications-and-standards/standards/ecma-376/) — package and document markup specifications.
- [Footnote element](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.footnote) — note content and type.
- [FootnoteReference element](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.footnotereference) — a body reference to a note ID.
- [FootnoteReferenceMark element](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.footnotereferencemark) — the marker within a footnote.

These links are design references, not a claim that every supported Word version has been tested. Microsoft Word rendering validation was not performed for this release.
