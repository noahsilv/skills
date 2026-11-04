#!/usr/bin/env python3
"""Synthetic example checker: CSV shape only, no financial validation."""

import csv
import hashlib
import io
import json
from pathlib import Path
import sys


def inspect(path):
    data = Path(path).read_bytes()
    rows = list(csv.reader(io.StringIO(data.decode("utf-8")), strict=True))
    valid = bool(rows) and rows[0] == ["account", "amount"] and len(rows) > 1 and all(len(row) == 2 for row in rows[1:])
    return {"check": "csv-shape", "status": "pass" if valid else "fail", "data_row_count": max(0, len(rows) - 1), "artifact_sha256": hashlib.sha256(data).hexdigest(), "scope": "CSV header, row width, and at least one data row only."}


if __name__ == "__main__":
    result = inspect(sys.argv[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "pass" else 1)
