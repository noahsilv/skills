# Office package audit

Inspect Office Open XML files without changing them. This Python tool checks selected structures and lists content a reviewer may otherwise overlook. It requires no third-party Python dependencies and makes no network calls.

Run with Python 3.10 or newer:

```sh
python scripts/audit.py report.docx > audit.json
python -m unittest discover -s tests -v
```

Paths can be absolute or relative to the current directory. The report is always JSON on standard output. Exit 0 means the implemented checks passed, 1 means content review is needed, and 2 means inspection failed or detected a structural error. `status: unsupported` also exits 2.

## Demonstration

Create these synthetic files in a new local scratch directory:

```sh
python examples/make_examples.py /tmp/office-audit-demo
python scripts/audit.py /tmp/office-audit-demo/clean.docx
python scripts/audit.py /tmp/office-audit-demo/review.xlsx
python scripts/audit.py /tmp/office-audit-demo/broken.docx
```

Expected exits are 0, 1 and 2 respectively. Run each command even though the latter two deliberately return a nonzero status. The second file contains a hidden sheet and synthetic metadata. The third has a broken main-document relationship. The generator refuses to overwrite existing demonstration files.

## What is checked

- ZIP member paths, exact and ASCII case-equivalent duplicates, original names before ZIP-library normalization, encryption flags, supported compression, CRC/read failures and resource limits.
- XML parsing, including relationship and VML parts. DTD and entity declarations are rejected.
- Content-type declarations, the prescribed relationship content type, relationship IDs, consuming `r:id`/`r:embed`/`r:link` references, internal target resolution and a required Office main part matching the extension.
- Explicit worksheet row/cell indexes, stored formula syntax markers, linked shared-string indexes and duplicate spreadsheet drawing shape IDs.
- Metadata (including Transitional and Strict property namespaces at arbitrary part names), comment-related parts, tracked changes, hidden text properties, hidden spreadsheet items, hidden slides, speaker notes, custom XML, chart/pivot/connection data and external relationship presence.
- Binary and other non-XML members are identified as uninspected content. Their archive integrity is checked; their contents are not interpreted.

Findings include `severity`, `code`, `member`, `locator`, `message` and, where useful, `count`. Locations use XML paths or named element patterns. The report includes the input SHA-256, XML inspection count and uninspected members. Metadata values, document text and external URL values are omitted; file and member names remain visible.

## Supported formats and bounds

The command accepts `.docx`, `.docm`, `.dotx`, `.dotm`, `.xlsx`, `.xlsm`, `.xltx`, `.xltm`, `.pptx`, `.pptm`, `.potx` and `.potm`. Legacy `.doc`, `.xls`, `.ppt`, PDFs, password-encrypted Office containers, encrypted ZIP members and unsupported compression are rejected rather than treated as clean.

Default bounds are 64 MiB compressed input, 5,000 members, 16 MiB expanded per member, 128 MiB expanded in total, and a 200:1 maximum member compression ratio. A large legitimate file can exceed these bounds. A preflight failure means members were not inspected. Importing `inspect_file(path, Limits(...))` permits an explicitly chosen bounded configuration; the CLI uses the defaults.

The tool does not extract files, follow relationships, launch Office or execute macros. It reads the input into a bounded snapshot, so the SHA-256 and findings refer to the same bytes.

## Limits

This is neither a full OOXML schema validator nor a content-classification or sanitization system. Review-surface detection covers the listed representations and common package structures; arbitrary XML can contain additional data. Every included file still needs appropriate substantive review. Images, encrypted content and embedded binaries need other tools. A clean result does not prove confidentiality, authenticity, absence of malware, accessibility, rendering quality or application compatibility. Metadata cannot establish whether a person or an AI wrote the content, and this tool makes no authorship claim.

The synthetic tests check implemented behavior and failure paths. They do not establish native Word, Excel or PowerPoint interoperability. Application opening/rendering and workbook recalculation are separate checks on the final saved artifact. No existing finding is suppressed because it also occurs in an older file.

The package was independently implemented for this portfolio using standard Python ZIP/XML facilities and the public Office package structure. It includes only text source and synthetic fixture generation, with no real source documents or binary templates.
