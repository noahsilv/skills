#!/usr/bin/env python3
"""Run each package's unittest suite without import-name collisions."""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    suites = sorted((ROOT / "skills").glob("*/tests/test_*.py"))
    expected = {p.parent.parent.name for p in (ROOT / "skills").glob("*/scripts/*.py")}
    present = {p.parent.parent.name for p in suites}
    if present != expected:
        print("FAIL: missing or unexpected executable test packages:", sorted(present ^ expected))
        return 1
    failures = []
    total = 0
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for folder in sorted({path.parent for path in suites}):
        print(f"Running {folder.relative_to(ROOT)}", flush=True)
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(folder), "-p", "test_*.py", "-v"], cwd=ROOT, env=environment, text=True, capture_output=True)
        output = result.stdout + result.stderr
        print(output, end="", flush=True)
        counts = re.findall(r"Ran (\d+) tests?", output)
        count = int(counts[-1]) if counts else 0
        total += count
        if result.returncode or count == 0:
            failures.append(str(folder.relative_to(ROOT)))
    if failures:
        print("FAIL:", ", ".join(failures))
        return 1
    print(f"PASS: {total} tests in {len({path.parent for path in suites})} executable package suites. Prompt evaluations are recorded separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
