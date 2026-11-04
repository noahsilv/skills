#!/usr/bin/env python3
"""Validate this collection's metadata, relative Markdown links and manifest."""
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[1]
from build_catalog import REGISTRY, build

SKILLS = set(REGISTRY)
IGNORED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "dist"}
ALLOWED_SUFFIXES = {".md", ".py", ".json", ".txt", ".yml", ".yaml", ".csv"}


def source_files():
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"symlink not allowed: {relative}")
        if path.is_file():
            yield path


def validate(check_manifest=False):
    errors = []
    try:
        if (ROOT / "catalog" / "skills.json").read_text() != build():
            errors.append("catalog is stale; run scripts/build_catalog.py")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"catalog invalid: {exc}")
    names = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir() and p.name not in IGNORED_DIRS}
    if names != SKILLS:
        errors.append(f"unexpected skill membership: {sorted(names ^ SKILLS)}")
    for name in sorted(SKILLS):
        path = ROOT / "skills" / name / "SKILL.md"
        if not path.is_file():
            errors.append(f"missing skill: {name}")
            continue
        content = path.read_text(encoding="utf-8")
        match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", content, re.S)
        try:
            meta = yaml.safe_load(match.group(1)) if match else None
            if not isinstance(meta, dict) or meta.get("name") != name:
                raise ValueError("missing or inconsistent name")
            description = meta.get("description")
            if not isinstance(description, str) or not description.strip() or len(description) > 1024:
                raise ValueError("description must contain 1–1024 characters")
            allowed = {"name", "description", "compatibility", "metadata", "license"}
            if set(meta) - allowed:
                raise ValueError("unexpected metadata fields")
        except (ValueError, yaml.YAMLError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")
    try:
        files = list(source_files())
    except ValueError as exc:
        return [str(exc)]
    for path in files:
        rel = path.relative_to(ROOT)
        if path.suffix not in ALLOWED_SUFFIXES and path.name != "LICENSE" and str(rel) != ".gitignore":
            errors.append(f"unexpected file type: {rel}")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError:
            errors.append(f"non-UTF8 file: {rel}")
            continue
        if "\x00" in content:
            errors.append(f"binary content: {rel}")
        if path.suffix == ".py":
            try:
                ast.parse(content, filename=str(rel))
            except SyntaxError as exc:
                errors.append(f"Python syntax: {rel}: {exc}")
        if path.suffix == ".json":
            try:
                json.loads(content)
            except ValueError as exc:
                errors.append(f"JSON syntax: {rel}: {exc}")
        if path.suffix == ".md":
            for target in re.findall(r"(?<!!)\[[^\]]*\]\(([^\s)]+)\)", content):
                if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                    continue
                target = unquote(target.split("#")[0])
                resolved = (path.parent / target).resolve()
                if not resolved.is_relative_to(ROOT) or not resolved.exists():
                    errors.append(f"broken or escaping link: {rel}: {target}")
    if check_manifest:
        try:
            manifest = json.loads((ROOT / "release-manifest.json").read_text())
            expected = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
            if len(expected) != len(manifest["files"]):
                raise ValueError("duplicate manifest paths")
            actual = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.relative_to(ROOT).as_posix() != "release-manifest.json"}
            if actual != expected:
                missing = sorted(set(expected) - set(actual))
                extra = sorted(set(actual) - set(expected))
                changed = sorted(k for k in actual.keys() & expected.keys() if actual[k] != expected[k])
                errors.append(f"manifest mismatch: missing={missing}, extra={extra}, changed={changed}")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"invalid manifest: {exc}")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="store_true")
    args = parser.parse_args()
    findings = validate(args.manifest)
    for finding in findings:
        print("FAIL:", finding)
    if not findings:
        print(f"PASS: {len(SKILLS)} skill packages; metadata, syntax and local links" + ("; release manifest" if args.manifest else ""))
    raise SystemExit(bool(findings))
