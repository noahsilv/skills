#!/usr/bin/env python3
"""Build the public skill catalog from reviewed package metadata."""
import argparse
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
# Reviewed discovery aliases and executable demonstration requirements.
REGISTRY = {
    "actuals-update-planner": (["plan an actuals update"], ["python3.11", "openpyxl"]),
    "artifact-quality-gate": (["verify current check evidence"], ["python3.11"]),
    "debt-schedule": (["loan amortization"], ["python3.11"]),
    "diligence-request-tracker": (["information request roundtrip"], ["python3.11"]),
    "document-review-coverage": (["check reviewer coverage"], ["python3.11"]),
    "docx-footnotes": (["insert native citations"], ["python3.11"]),
    "evidence-brief": (["draft a decision brief"], []),
    "evidence-ledger": (["maintain sourced claims"], ["python3.11"]),
    "financial-statement-analysis": (["analyze normalized statements"], ["python3.11"]),
    "model-regression-testing": (["compare model snapshots"], ["python3.11"]),
    "office-package-audit": (["inspect Office package structure"], ["python3.11"]),
    "prompt-optimizer": (["improve a prompt"], []),
    "scenario-analysis": (["compare financial cases"], ["python3.11"]),
    "skill-router": (["find a workflow"], ["python3.11"]),
    "workbook-tieout": (["reconcile spreadsheet cells"], ["python3.11", "openpyxl"]),
}


def build():
    actual = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
    if actual != set(REGISTRY):
        raise ValueError(f"catalog membership differs: {sorted(actual ^ set(REGISTRY))}")
    entries = []
    for name, (aliases, capabilities) in sorted(REGISTRY.items()):
        path = ROOT / "skills" / name / "SKILL.md"
        match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", path.read_text(), re.S)
        if not match:
            raise ValueError(f"missing metadata: {name}")
        metadata = yaml.safe_load(match.group(1))
        if not isinstance(metadata, dict) or metadata.get("name") != name or not isinstance(metadata.get("description"), str):
            raise ValueError(f"invalid metadata: {name}")
        entries.append({"id": name, "path": str(path.relative_to(ROOT)), "description": metadata["description"], "aliases": aliases, "required_capabilities": capabilities})
    return json.dumps({"schema_version": 1, "skills": entries}, indent=2, ensure_ascii=False) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        content = build()
        output = ROOT / "catalog" / "skills.json"
        if args.check:
            if not output.exists() or output.read_text() != content:
                raise ValueError("catalog is stale; run scripts/build_catalog.py")
            print("PASS: catalog matches package descriptions and routing registry")
        else:
            output.parent.mkdir(exist_ok=True)
            output.write_text(content)
            print(f"Wrote catalog for {len(REGISTRY)} skills")
        return 0
    except (ValueError, OSError, yaml.YAMLError) as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
