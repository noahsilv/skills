#!/usr/bin/env python3
"""Create a minimal synthetic .docx with two explicit footnote markers."""
from pathlib import Path
import sys
import zipfile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"


def make_example(path):
    parts = {
        "[Content_Types].xml": f'''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="{CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>''',
        "_rels/.rels": f'''<Relationships xmlns="{R}"><Relationship Id="rId1" Type="{OFFICE}officeDocument" Target="word/document.xml"/></Relationships>''',
        "word/document.xml": f'''<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{W}" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" mc:Ignorable="w14"><w:body><w:p><w:r><w:t>This document is a synthetic example.</w:t></w:r><w:r><w:t>[[fn:purpose]]</w:t></w:r></w:p><w:p><w:r><w:t>No real project data is included.</w:t></w:r><w:r><w:t>[[fn:data]]</w:t></w:r></w:p><w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>''',
    }
    with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as z:
        for name, value in parts.items():
            z.writestr(name, value.encode("utf-8"))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python make_example.py NEW.docx")
    make_example(Path(sys.argv[1]))
