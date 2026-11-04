#!/usr/bin/env python3
"""Generate small synthetic packages for local demonstrations and tests.

These demonstrate the inspector's scope; they are not a native Office
interoperability certification corpus. No real documents are distributed.
"""

import argparse
from pathlib import Path
import zipfile

CT = "http://schemas.openxmlformats.org/package/2006/content-types"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"


def package_parts(kind="word"):
    main, main_type, content = {
        "word": ("word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
                 f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>Synthetic example.</w:t></w:r></w:p></w:body></w:document>'),
        "excel": ("xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
                  f'<workbook xmlns="{S}" xmlns:r="{R}"><sheets><sheet name="Example" sheetId="1" r:id="rId1"/></sheets></workbook>'),
        "powerpoint": ("ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
                       f'<p:presentation xmlns:p="{P}"/>'),
    }[kind]
    parts = {
        "[Content_Types].xml": f'<Types xmlns="{CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/{main}" ContentType="{main_type}"/></Types>',
        "_rels/.rels": f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="{main}"/></Relationships>',
        main: content,
    }
    if kind == "excel":
        parts["xl/_rels/workbook.xml.rels"] = f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{R}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
        parts["xl/worksheets/sheet1.xml"] = f'<worksheet xmlns="{S}"><sheetData><row r="1"><c r="A1"><v>12</v></c></row></sheetData></worksheet>'
        parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace("</Types>", '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
    return parts


def write_package(path, parts, compression=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    names = ["clean.docx", "review.xlsx", "broken.docx"]
    if any((args.output / name).exists() for name in names):
        parser.error("Use an output directory without existing demonstration files.")
    write_package(args.output / names[0], package_parts())
    review = package_parts("excel")
    review["xl/workbook.xml"] = review["xl/workbook.xml"].replace('name="Example"', 'name="Example" state="hidden"')
    review["docProps/custom.xml"] = '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"><property name="Demo"><value>Synthetic metadata for review.</value></property></Properties>'
    write_package(args.output / names[1], review)
    broken = package_parts()
    del broken["word/document.xml"]
    write_package(args.output / names[2], broken)
    print("Created clean.docx (expected exit 0), review.xlsx (1), broken.docx (2).")


if __name__ == "__main__":
    main()
