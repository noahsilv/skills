#!/usr/bin/env python3
"""Bind review records to a text artifact and reconcile declared review slots.

Only mechanical properties are checked. A matching quotation does not prove
that a proposed revision follows from it or that the reviewer judged correctly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import re
import sys

MAX_TEXT_BYTES = 1_048_576
MAX_JSON_BYTES = 4_194_304
MAX_LINES = 20_000
MAX_UNITS = 5_000
MAX_UNIT_CHARS = 40_000
MAX_CHECKS = 12
MAX_RECORDS = 20_000
MAX_EVIDENCE_FILES = 16
MAX_SUPPORTS_PER_RECORD = 16
CHECK_ID = re.compile(r"[a-z][a-z0-9-]{0,47}\Z")
SOURCE_ID = re.compile(r"[A-Z][A-Z0-9_-]{0,31}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
VERDICTS = {"no-change", "revise", "needs-evidence", "not-applicable"}
STATUSES = {"open", "responded", "closed"}
LIMITATION = (
    "Counts measure valid submitted records, not review quality. Exact quotations "
    "establish text presence only. Factual support, judgment correctness, response "
    "adequacy, and implementation of proposed changes are NOT_ASSESSED."
)


class InputError(ValueError):
    """An input is unsupported, malformed, or exceeds a documented limit."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_bytes(path: Path, limit: int) -> bytes:
    if not path.is_file():
        raise InputError(f"Not a regular file: {path.name}")
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise InputError(f"File exceeds {limit} bytes: {path.name}")
    return raw


def read_text(path: Path) -> tuple[bytes, str]:
    if path.suffix.lower() not in {".md", ".txt"}:
        raise InputError(f"Only .md and .txt source files are supported: {path.name}")
    raw = read_bytes(path, MAX_TEXT_BYTES)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"Source is not UTF-8: {path.name}") from exc
    if "\x00" in text:
        raise InputError(f"NUL bytes are not supported: {path.name}")
    return raw, text


def unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(raw: bytes, name: str) -> dict:
    try:
        value = json.loads(
            raw, object_pairs_hook=unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(InputError(f"Invalid JSON constant: {value}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InputError(f"Invalid JSON: {name}") from exc
    if not isinstance(value, dict):
        raise InputError(f"JSON root must be an object: {name}")
    return value


def load_json(path: Path) -> dict:
    return parse_json(read_bytes(path, MAX_JSON_BYTES), path.name)


def checks_list(checks: object) -> list[str]:
    if not isinstance(checks, list) or not 1 <= len(checks) <= MAX_CHECKS:
        raise InputError(f"Supply between 1 and {MAX_CHECKS} review checks")
    if any(not isinstance(item, str) or not CHECK_ID.fullmatch(item) for item in checks):
        raise InputError("Check names must be lowercase identifiers, at most 48 characters")
    if len(set(checks)) != len(checks):
        raise InputError("Review checks must be unique")
    return checks


def inventory(source: Path, checks: list[str]) -> dict:
    checks = checks_list(checks)
    raw, text = read_text(source)
    # Split only at LF; a CRLF pair remains intact inside the unit text/hash.
    if "\r" in text.replace("\r\n", ""):
        raise InputError("Only LF or CRLF line endings are supported")
    parts = text.split("\n")
    lines = [line + "\n" for line in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    if len(lines) > MAX_LINES:
        raise InputError(f"Source exceeds {MAX_LINES} physical lines")
    units, blank_lines, pending = [], [], []
    first_line = 1

    def flush(end_line: int) -> None:
        nonlocal pending
        if not pending:
            return
        unit_text = "".join(pending)
        if len(unit_text) > MAX_UNIT_CHARS:
            raise InputError(f"A text block exceeds {MAX_UNIT_CHARS} characters; add explicit blank-line boundaries")
        units.append({
            "id": f"U{len(units) + 1:04d}", "start_line": first_line,
            "end_line": end_line, "sha256": digest(unit_text.encode("utf-8")),
            "text": unit_text,
        })
        pending = []

    for number, line in enumerate(lines, 1):
        if not line.strip():
            flush(number - 1)
            blank_lines.append(number)
        else:
            if not pending:
                first_line = number
            pending.append(line)
    flush(len(lines))
    if not units:
        raise InputError("Source contains no reviewable text blocks")
    if len(units) > MAX_UNITS or len(units) * len(checks) > MAX_RECORDS:
        raise InputError("Source/check combination exceeds the bounded review size")
    return {
        "schema_version": 1, "segmentation": "nonblank-blocks-v1", "checks": checks,
        "source": {"name": source.name, "sha256": digest(raw), "bytes": len(raw), "lines": len(lines)},
        "blank_lines": blank_lines, "units": units,
    }


def require_keys(value: dict, required: set[str], optional: set[str], context: str) -> None:
    if not required.issubset(value) or set(value) - required - optional:
        raise InputError(f"Unexpected or missing fields in {context}")


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def sha(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def read_evidence(declarations: list, base: Path) -> tuple[dict, list[dict]]:
    sources, problems = {}, []
    seen = set()
    for index, declaration in enumerate(declarations, 1):
        try:
            if not isinstance(declaration, dict):
                raise InputError("Evidence declaration must be an object")
            require_keys(declaration, {"id", "path", "sha256"}, set(), "evidence declaration")
            source_id, rel = declaration["id"], declaration["path"]
            if not isinstance(source_id, str) or not SOURCE_ID.fullmatch(source_id) or source_id == "DRAFT":
                raise InputError("Evidence ID must be an uppercase identifier other than DRAFT")
            if source_id in seen:
                sources.pop(source_id, None)
                raise InputError(f"Duplicate evidence ID: {source_id}")
            seen.add(source_id)
            if not nonempty(rel) or "\\" in rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
                raise InputError("Evidence paths must be relative paths without '..' or backslashes")
            path = (base / rel).resolve()
            if not path.is_relative_to(base.resolve()):
                raise InputError("Evidence path leaves the review directory")
            if not sha(declaration["sha256"]):
                raise InputError("Evidence needs a lowercase SHA-256 hash")
            raw, text = read_text(path)
            if digest(raw) != declaration["sha256"]:
                raise InputError(f"Evidence file changed: {source_id}")
            sources[source_id] = text
        except (InputError, OSError, ValueError) as exc:
            problems.append({"code": "EVIDENCE_INVALID", "evidence": index, "message": str(exc)})
    return sources, problems


def validate_record(record: object, units: dict, checks: list, evidence: dict) -> tuple[str, str]:
    if not isinstance(record, dict):
        raise InputError("Review record must be an object")
    require_keys(
        record, {"unit_id", "check", "reviewer", "verdict", "quote", "comment", "status"},
        {"proposed_text", "support", "resolution", "response"}, "review record",
    )
    unit_id, check = record["unit_id"], record["check"]
    if not isinstance(unit_id, str) or unit_id not in units:
        raise InputError("Unknown unit_id")
    if not isinstance(check, str) or check not in checks:
        raise InputError("Unknown review check")
    if not all(nonempty(record[field]) for field in ("reviewer", "quote", "comment")):
        raise InputError("reviewer, quote, and comment must be nonempty strings")
    if record["quote"] not in units[unit_id]["text"]:
        raise InputError("Review quote is not an exact span of this unit")
    if not isinstance(record["verdict"], str) or record["verdict"] not in VERDICTS:
        raise InputError("Unknown verdict")
    if not isinstance(record["status"], str) or record["status"] not in STATUSES:
        raise InputError("Unknown status")
    if record["status"] == "closed" and not nonempty(record.get("resolution")):
        raise InputError("A closed record needs a resolution note")
    if "resolution" in record and not nonempty(record["resolution"]):
        raise InputError("resolution must be a nonempty string when supplied")
    if record["status"] == "responded" and not nonempty(record.get("response")):
        raise InputError("A responded record needs a response separate from the original comment")
    if "response" in record and not nonempty(record["response"]):
        raise InputError("response must be a nonempty string when supplied")
    if record["verdict"] == "needs-evidence" and record["status"] == "closed":
        raise InputError("needs-evidence cannot be closed; record the resulting assessment first")
    support = record.get("support", [])
    if not isinstance(support, list) or len(support) > MAX_SUPPORTS_PER_RECORD:
        raise InputError("support must be a bounded list")
    if record["verdict"] == "revise":
        if not nonempty(record.get("proposed_text")) or not support:
            raise InputError("A revision needs proposed_text and at least one support quotation")
    elif "proposed_text" in record:
        raise InputError("Only a revise record may contain proposed_text")
    for citation in support:
        if not isinstance(citation, dict):
            raise InputError("Support citation must be an object")
        require_keys(citation, {"source_id", "quote"}, {"unit_id", "locator"}, "support citation")
        source_id = citation["source_id"]
        if not nonempty(source_id) or not nonempty(citation["quote"]):
            raise InputError("Support source_id and quote must be nonempty strings")
        if "locator" in citation and not nonempty(citation["locator"]):
            raise InputError("Support locator must be a nonempty string when supplied")
        if source_id == "DRAFT":
            support_unit = citation.get("unit_id")
            if not isinstance(support_unit, str) or support_unit not in units:
                raise InputError("DRAFT support needs an existing unit_id")
            source_text = units[support_unit]["text"]
        else:
            if "unit_id" in citation or source_id not in evidence:
                raise InputError("Evidence citation needs a current declared source and no unit_id")
            source_text = evidence[source_id]
        if citation["quote"] not in source_text:
            raise InputError("Support quotation is not an exact span of the named current source")
    return unit_id, check


def reconcile(source: Path, manifest_path: Path, review_path: Path) -> dict:
    # Parse and hash one snapshot: the review binds the complete saved inventory,
    # including the declared checks, not merely the document text it describes.
    manifest_raw = read_bytes(manifest_path, MAX_JSON_BYTES)
    manifest = parse_json(manifest_raw, manifest_path.name)
    manifest_hash = digest(manifest_raw)
    reviews = load_json(review_path)
    require_keys(manifest, {"schema_version", "segmentation", "checks", "source", "blank_lines", "units"}, set(), "inventory")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise InputError("Only inventory schema_version 1 is supported")
    if not isinstance(manifest["source"], dict) or not sha(manifest["source"].get("sha256")):
        raise InputError("Inventory needs a source object with a lowercase SHA-256 hash")
    current = inventory(source, checks_list(manifest.get("checks")))
    require_keys(reviews, {"schema_version", "source_sha256", "inventory_sha256", "records"}, {"evidence"}, "review ledger")
    if type(reviews["schema_version"]) is not int or reviews["schema_version"] != 1:
        raise InputError("Only review schema_version 1 is supported")
    if not sha(reviews["source_sha256"]):
        raise InputError("Review ledger needs a lowercase source_sha256")
    if not sha(reviews["inventory_sha256"]):
        raise InputError("Review ledger needs a lowercase inventory_sha256")
    records, declarations = reviews["records"], reviews.get("evidence", [])
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise InputError(f"records must be a list with at most {MAX_RECORDS} items")
    if not isinstance(declarations, list) or len(declarations) > MAX_EVIDENCE_FILES:
        raise InputError(f"evidence must be a list with at most {MAX_EVIDENCE_FILES} files")
    diagnostics = []
    declared_source = manifest.get("source", {})
    declared_hash = declared_source.get("sha256") if isinstance(declared_source, dict) else None
    if declared_hash != current["source"]["sha256"]:
        diagnostics.append({"code": "SOURCE_CHANGED", "message": "The inventory does not describe the current source bytes."})
    elif json.dumps(manifest, sort_keys=True) != json.dumps(current, sort_keys=True):
        diagnostics.append({"code": "INVENTORY_MISMATCH", "message": "Inventory fields do not match a fresh inventory of the source."})
    if reviews["source_sha256"] != current["source"]["sha256"]:
        diagnostics.append({"code": "REVIEW_SOURCE_MISMATCH", "message": "The ledger is not bound to the current source bytes."})
    if reviews["inventory_sha256"] != manifest_hash:
        diagnostics.append({"code": "REVIEW_INVENTORY_MISMATCH", "message": "The ledger is not bound to these exact inventory bytes and review checks."})
    report = {
        "schema_version": 1, "source": current["source"], "inventory_source_sha256": declared_hash,
        "ledger_source_sha256": reviews["source_sha256"], "source_binding": "CURRENT" if not diagnostics else "UNVERIFIED",
        "inventory_sha256": manifest_hash, "ledger_inventory_sha256": reviews["inventory_sha256"],
        "coverage_status": "UNVERIFIED", "review_conclusion": "NOT_ASSESSED", "limitation": LIMITATION,
        "counts": {"expected_pairs": len(current["units"]) * len(current["checks"]), "submitted_records": len(records), "valid_unique_pairs": 0},
        "checks": current["checks"], "units": current["units"], "blank_lines": current["blank_lines"],
        "diagnostics": diagnostics, "missing_pairs": [], "accepted_record_numbers": [],
        "reviewer_status_counts": {}, "manual_review_record_numbers": list(range(1, len(records) + 1)), "records": records,
    }
    if diagnostics:
        # Old anchors or scope cannot be reconciled against a changed artifact.
        # Do not count records from a different source or review inventory.
        return report
    evidence, evidence_problems = read_evidence(declarations, review_path.parent)
    diagnostics.extend(evidence_problems)
    units = {unit["id"]: unit for unit in current["units"]}
    expected = {(unit_id, check) for unit_id in units for check in current["checks"]}
    candidates = {}
    pair_counts = Counter()
    for record in records:
        if isinstance(record, dict) and isinstance(record.get("unit_id"), str) and isinstance(record.get("check"), str):
            pair_counts[(record["unit_id"], record["check"])] += 1
    for number, record in enumerate(records, 1):
        try:
            pair = validate_record(record, units, current["checks"], evidence)
            if pair_counts[pair] != 1:
                raise InputError("Duplicate unit/check pair; no duplicate is counted")
            candidates[pair] = number
        except InputError as exc:
            diagnostics.append({"code": "RECORD_INVALID", "record": number, "message": str(exc)})
    report["missing_pairs"] = [{"unit_id": unit_id, "check": check} for unit_id, check in sorted(expected - set(candidates))]
    report["accepted_record_numbers"] = sorted(candidates.values())
    report["counts"]["valid_unique_pairs"] = len(candidates)
    accepted = [(number, records[number - 1]) for number in sorted(candidates.values())]
    report["reviewer_status_counts"] = dict(sorted(Counter(row["status"] for _, row in accepted).items()))
    open_work = {
        number for number, row in accepted
        if row["verdict"] in {"revise", "needs-evidence"} or row["status"] != "closed"
    }
    invalid_work = set(range(1, len(records) + 1)) - set(report["accepted_record_numbers"])
    report["manual_review_record_numbers"] = sorted(open_work | invalid_work)
    report["coverage_status"] = "COMPLETE" if not diagnostics and not report["missing_pairs"] else "INCOMPLETE"
    return report


def code_block(text: object) -> str:
    value = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
    return "\n".join("    " + line for line in value.splitlines()) + "\n"


def render(report: dict) -> str:
    counts = report["counts"]
    accepted_numbers = set(report["accepted_record_numbers"])
    lines = [
        "# Document review record reconciliation", "",
        f"Source/inventory binding: **{report['source_binding']}**. Coverage: **{report['coverage_status']}**.",
        "Judgment conclusion: **NOT_ASSESSED**.", "", report["limitation"], "",
        "Current source:", "", code_block(report["source"]["name"]),
        f"Current source SHA-256: `{report['source']['sha256']}`",
        f"Source SHA-256 recorded in inventory: `{report['inventory_source_sha256']}`",
        f"Source SHA-256 recorded in ledger: `{report['ledger_source_sha256']}`", "",
        f"Current inventory file SHA-256: `{report['inventory_sha256']}`",
        f"Inventory file SHA-256 recorded in ledger: `{report['ledger_inventory_sha256']}`", "",
        f"Expected unit/check pairs: {counts['expected_pairs']}. Submitted records: {counts['submitted_records']}. Valid unique pairs: {counts['valid_unique_pairs']}.",
        f"Excluded blank physical lines: {len(report['blank_lines'])}. No content block is exempted by the program.", "",
        "## Inventory", "", "| Unit | Physical lines | Unit SHA-256 |", "| --- | --- | --- |",
    ]
    for unit in report["units"]:
        lines.append(f"| {unit['id']} | {unit['start_line']}–{unit['end_line']} | `{unit['sha256']}` |")
    lines += ["", "## Missing records", ""]
    if report["source_binding"] != "CURRENT":
        lines.append("Not reconciled: first inventory and review the current artifact.")
    elif report["missing_pairs"]:
        lines.extend(f"- {item['unit_id']} / {item['check']}" for item in report["missing_pairs"])
    else:
        lines.append("None among the declared unit/check pairs.")
    lines += ["", "## Mechanical diagnostics", ""]
    if report["diagnostics"]:
        for diagnostic in report["diagnostics"]:
            lines += [code_block(json.dumps(diagnostic, ensure_ascii=False))]
    else:
        lines.append("No mechanical exceptions found within the documented checks.")
    lines += ["", "## Review work", ""]
    lines.append("Recorded reviewer statuses: " + json.dumps(report["reviewer_status_counts"], sort_keys=True) + ".")
    lines.append("Records needing a person to assess a proposal, evidence gap, open response, or invalid/stale record: " + (", ".join(map(str, report["manual_review_record_numbers"])) or "none identified by these checks") + ".")
    lines.append("Closed is a ledger status with a supplied resolution note. It does not prove a response was accepted or a change was implemented.")
    lines += ["", "## Reviewer records (as supplied)", ""]
    for number, record in enumerate(report["records"], 1):
        accepted = number in accepted_numbers
        lines += [f"### Record {number} — {'counted' if accepted else 'not counted'}", "", code_block(json.dumps(record, ensure_ascii=False, indent=2))]
    return "\n".join(lines) + "\n"


def write_new(path: Path, text: str) -> None:
    # Exclusive creation protects existing files, including symlinks/hardlinks.
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("inventory", help="Inventory contiguous nonblank text blocks")
    build.add_argument("source", type=Path)
    build.add_argument("--checks", nargs="+", default=["clarity", "source-support"])
    build.add_argument("--out", type=Path, required=True)
    compare = commands.add_parser("reconcile", help="Reconcile reviewer records against the current source")
    compare.add_argument("source", type=Path)
    compare.add_argument("inventory", type=Path)
    compare.add_argument("reviews", type=Path)
    compare.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            result = inventory(args.source, args.checks)
            serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            write_new(args.out, serialized)
            print(f"Inventoried {len(result['units'])} blocks and {len(result['checks'])} checks: {args.out}")
            print(f"Inventory SHA-256: {digest(serialized.encode('utf-8'))}")
            return 0
        report = reconcile(args.source, args.inventory, args.reviews)
        args.out_dir.mkdir(exist_ok=False)
        write_new(args.out_dir / "report.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        write_new(args.out_dir / "report.md", render(report))
        print(f"{report['coverage_status']}; judgment NOT_ASSESSED: {args.out_dir / 'report.md'}")
        return 0 if report["coverage_status"] == "COMPLETE" else 2
    except (InputError, OSError, ValueError) as exc:
        print(f"Input/output error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
