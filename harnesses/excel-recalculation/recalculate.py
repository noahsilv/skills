"""Recalculate the public fixtures with an isolated LibreOffice profile."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

from workbook import prepare, verify


def calculate():
    engine = shutil.which("soffice") or shutil.which("libreoffice")
    if not engine:
        raise ValueError("Install LibreOffice Calc and put soffice or libreoffice on PATH")
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder).resolve()
        output = root / "calculated"
        output.mkdir()
        versions = ("baseline", "challenge")
        originals = []
        for version in versions:
            source = root / f"{version}.xlsx"
            prepare(source, version)
            if verify(source, version)["status"] != "INCOMPLETE":
                raise ValueError("A new fixture unexpectedly includes saved results")
            originals.append(hashlib.sha256(source.read_bytes()).digest())
        profile = "-env:UserInstallation=" + (root / "profile").as_uri()
        identity = subprocess.run([engine, profile, "--version"], capture_output=True, text=True,
                                  check=True, timeout=30).stdout.strip()
        paths = [root / f"{version}.xlsx" for version in versions]
        subprocess.run([engine, profile, "--headless", "--convert-to", "xlsx:Calc MS Excel 2007 XML",
                        "--outdir", str(output), *(str(path) for path in paths)],
                       capture_output=True, text=True, check=True, timeout=120)
        results = []
        for version, path, digest in zip(versions, paths, originals, strict=True):
            if hashlib.sha256(path.read_bytes()).digest() != digest:
                raise ValueError("Calculation changed a source workbook")
            report = verify(output / path.name, version)
            if report["status"] != "VERIFIED":
                raise ValueError("The calculated copy has missing results")
            results.append(report)
        return {"engine": identity, "sources_preserved": True, "checks": results}
