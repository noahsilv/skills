#!/usr/bin/env python3
"""Generate a synthetic catalog in a new external directory and route its request."""

import argparse
import json
from pathlib import Path
import sys

import route


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        destination = route.no_symlinks(args.output_dir)
        package = Path(__file__).resolve().parents[1]
        route.require(not destination.is_relative_to(package), "demo output must be outside the skill package")
        route.require(destination.parent.is_dir(), "destination parent must already exist")
        destination.mkdir(exist_ok=False)
        examples = package / "examples"
        catalog_root = destination / "catalog-root"
        catalog_root.mkdir()
        for name in ("alpha", "beta", "gamma"):
            skill_dir = catalog_root / name
            skill_dir.mkdir()
            route.write_new(skill_dir / "SKILL.md", (examples / "templates" / f"{name}.txt").read_text(encoding="utf-8"))
        for name in ("catalog.json", "request.json"):
            route.write_new(destination / name, (examples / name).read_text(encoding="utf-8"))
        catalog = route.load_json(destination / "catalog.json")
        request = route.load_json(destination / "request.json")
        result = route.route(catalog, request, catalog_root)
        route.write_new(destination / "result.json", json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
        route.write_new(destination / "result.md", (examples / "output.md").read_text(encoding="utf-8"))
        print(json.dumps({"output_dir": str(destination), "result_path": str(destination / "result.json"), "candidate_count": result["candidate_count"], "suggestion_count": len(result["suggestions"])}))
        return 0
    except (route.ValidationError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
