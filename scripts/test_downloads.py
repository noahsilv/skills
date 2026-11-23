"""Run package tests on the verified contents of the published skill downloads."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from zipfile import ZipFile

from validate import DOWNLOADS, ROOT, source_files, verify_download


def main():
    sources = list(source_files())
    total = 0
    failed = []
    for relative, package in sorted(DOWNLOADS.items()):
        archive = ROOT / relative
        verify_download(archive, package, sources)
        with tempfile.TemporaryDirectory() as directory:
            # The verifier compared every name and byte with this package's
            # public source tree. Extract only after that check succeeds.
            with ZipFile(archive) as verified:
                verified.extractall(directory)
            extracted = Path(directory) / package
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
            env.pop("PYTHONOPTIMIZE", None)
            result = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
                cwd=extracted, env=env, capture_output=True, encoding="utf-8", errors="replace",
            )
            output = result.stdout + result.stderr
            match = re.search(r"^Ran (\d+) tests? in ", output, re.MULTILINE)
            count = int(match[1]) if match else 0
            if result.returncode or not count:
                failed.append(package)
                print(f"FAIL {package}\n{output}", flush=True)
            else:
                print(f"PASS {package}: {count} tests from the extracted archive", flush=True)
                total += count
    print(f"{total} tests passed in {len(DOWNLOADS) - len(failed)} of {len(DOWNLOADS)} downloads.")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
