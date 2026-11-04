#!/usr/bin/env python3
"""Run each package's unittest suite without import-name collisions."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    suites = sorted((ROOT / "skills").glob("*/tests/test_*.py"))
    expected = {"workbook-tieout", "model-regression-testing", "office-package-audit", "docx-footnotes"}
    present = {p.parent.parent.name for p in suites}
    if present != expected:
        print("FAIL: missing or unexpected executable test packages:", sorted(present ^ expected))
        return 1
    failures = []
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for folder in sorted({path.parent for path in suites}):
        print(f"Running {folder.relative_to(ROOT)}", flush=True)
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(folder), "-p", "test_*.py", "-v"], cwd=ROOT, env=environment)
        if result.returncode:
            failures.append(str(folder.relative_to(ROOT)))
    if failures:
        print("FAIL:", ", ".join(failures))
        return 1
    print(f"PASS: {len({path.parent for path in suites})} executable package test suites. Prompt evaluations are recorded separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
