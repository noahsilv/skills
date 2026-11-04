#!/usr/bin/env python3
"""Suggest skills from an explicit local catalog; never execute their instructions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys


class ValidationError(ValueError):
    """An input violates the public contract."""


MAX_JSON_BYTES = 2 * 1024 * 1024
SLUG = re.compile(r"[a-z0-9]+(?:[-.][a-z0-9]+)*\Z")
ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
ALIAS = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]*\Z")
STOPWORDS = frozenset("a an and are as at be by can do for from has have i in is it my of on or our please skill skills that the this to use we with would you".split())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def exact_keys(value: object, keys: set[str], label: str) -> dict:
    require(type(value) is dict, f"{label} must be an object")
    require(set(value) == keys, f"{label} keys must be exactly {sorted(keys)}")
    return value


def string(value: object, label: str, limit: int = 10000) -> str:
    require(type(value) is str and 0 < len(value) <= limit, f"{label} must be a nonempty string of at most {limit} characters")
    require(value == value.strip() and not any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value), f"{label} has surrounding whitespace, control characters, or invalid Unicode")
    return value


def pairs(items: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in items:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValidationError(f"nonfinite JSON number: {value}")


def no_symlinks(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    for part in [*reversed(absolute.parents), absolute]:
        require(not part.is_symlink(), f"symlink is not permitted: {part}")
    return absolute


def load_json(path: Path) -> object:
    path = no_symlinks(path)
    require(path.is_file(), f"JSON input is not a regular file: {path}")
    require(path.stat().st_size <= MAX_JSON_BYTES, "JSON input exceeds 2 MiB")
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_JSON_BYTES + 1)
        require(len(data) <= MAX_JSON_BYTES, "JSON input exceeds 2 MiB")
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValidationError(f"invalid UTF-8 JSON: {exc}") from exc


def relative_file(root: Path, value: object) -> Path:
    path = string(value, "skill path", 4096)
    parts = path.split("/")
    require(not PurePosixPath(path).is_absolute() and "\\" not in path and ":" not in path, "skill path must be POSIX relative")
    require(all(part not in ("", ".", "..") for part in parts), "skill path contains an empty, dot, or parent component")
    require(parts[-1] == "SKILL.md", "skill path must name SKILL.md")
    target = no_symlinks(root.joinpath(*parts))
    require(target.is_relative_to(root), "skill path escapes supplied root")
    require(target.is_file(), f"skill file is missing or not regular: {path}")
    return target


def tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def string_list(value: object, label: str, pattern: re.Pattern, max_items: int = 100) -> list[str]:
    require(type(value) is list and len(value) <= max_items, f"{label} must be a list of at most {max_items} items")
    seen = set()
    for item in value:
        string(item, label, 100)
        require(pattern.fullmatch(item) is not None, f"invalid {label}: {item}")
        require(item not in seen, f"duplicate {label}: {item}")
        seen.add(item)
    return value


def validate_catalog(catalog: object, root: Path) -> list[dict]:
    exact_keys(catalog, {"schema_version", "skills"}, "catalog")
    require(type(catalog["schema_version"]) is int and catalog["schema_version"] == 1, "catalog schema_version must be integer 1")
    entries = catalog["skills"]
    require(type(entries) is list and 1 <= len(entries) <= 1000, "catalog skills must have 1–1000 entries")
    root = no_symlinks(root)
    require(root.is_dir(), "root must be an existing directory")
    identities, paths, physical_files = {}, set(), set()
    validated = []
    for entry in entries:
        exact_keys(entry, {"id", "path", "description", "aliases", "required_capabilities"}, "skill entry")
        ident = string(entry["id"], "skill id", 100)
        require(ID.fullmatch(ident) is not None, "skill id must use lowercase kebab case")
        string(entry["description"], "description")
        aliases = string_list(entry["aliases"], "alias", ALIAS)
        string_list(entry["required_capabilities"], "capability", SLUG)
        for name in [ident, *aliases]:
            normalized = tokens(name)
            require(normalized not in identities, f"duplicate or ambiguous normalized name/alias: {name}")
            identities[normalized] = ident
        target = relative_file(root, entry["path"])
        require(target not in paths, f"duplicate skill path: {entry['path']}")
        info = target.stat()
        physical = (info.st_dev, info.st_ino)
        require(physical not in physical_files, "duplicate skill file via hard link")
        paths.add(target)
        physical_files.add(physical)
        validated.append({**entry, "_target": target})
    return validated


def validate_request(request: object) -> dict:
    exact_keys(request, {"schema_version", "query", "available_capabilities", "limit"}, "request")
    require(type(request["schema_version"]) is int and request["schema_version"] == 1, "request schema_version must be integer 1")
    string(request["query"], "query")
    require(type(request["limit"]) is int and 1 <= request["limit"] <= 5, "limit must be an integer from 1 to 5")
    string_list(request["available_capabilities"], "capability", SLUG)
    return request


def phrase_present(query: tuple[str, ...], phrase: tuple[str, ...]) -> bool:
    return any(query[index:index + len(phrase)] == phrase for index in range(len(query) - len(phrase) + 1))


def fingerprint(path: Path) -> str:
    no_symlinks(path)
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), "skill target must be a regular file")
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.fstat(stream.fileno())
    require((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "skill file changed while hashing")
    return digest


def route(catalog: object, request: object, root: Path) -> dict:
    entries = validate_catalog(catalog, root)
    request = validate_request(request)
    query = tokens(request["query"])
    meaningful = set(query) - STOPWORDS
    candidates = []
    for entry in entries:
        names = [entry["id"], *entry["aliases"]]
        named = sorted(name for name in names if phrase_present(query, tokens(name)))
        vocabulary = set(tokens(" ".join([*names, entry["description"]]))) - STOPWORDS
        matched = sorted(meaningful & vocabulary)
        if not named and not matched:
            continue
        specificity = max((len(tokens(name)) for name in named), default=0)
        candidates.append((bool(named), specificity, len(matched), entry["id"], entry, named, matched))
    candidates.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
    suggestions = []
    for _, _, score, _, entry, named, matched in candidates[:request["limit"]]:
        missing = sorted(set(entry["required_capabilities"]) - set(request["available_capabilities"]))
        suggestions.append({
            "id": entry["id"], "path": entry["path"],
            "match_kind": "named" if named else "lexical",
            "matched_names": named, "matched_terms": matched,
            "lexical_overlap": score,
            "missing_capabilities": missing,
            "capability_status": "missing_declared" if missing else "declared_available",
            "skill_sha256": fingerprint(entry["_target"]),
        })
    return {
        "schema_version": 1, "suggestions": suggestions,
        "candidate_count": len(candidates), "omitted_count": max(0, len(candidates) - request["limit"]),
        "method": "explicit_name_then_token_overlap",
        "assessment": "Deterministic suggestions, not semantic certainty. Capabilities are caller declarations; no tools or skill instructions were executed.",
    }


def write_new(path: Path, data: str) -> None:
    target = no_symlinks(path)
    require(target.parent.is_dir(), "output parent directory must already exist")
    # O_EXCL refuses existing files, including a hard link to an input.
    with target.open("x", encoding="utf-8") as stream:
        stream.write(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = route(load_json(args.catalog), load_json(args.request), args.root)
        rendered = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            write_new(args.output, rendered)
        else:
            print(rendered, end="")
        return 0
    except (ValidationError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
