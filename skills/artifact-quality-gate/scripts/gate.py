#!/usr/bin/env python3
"""Bind self-reported check records to a frozen run and current local file bytes."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import uuid


class ValidationError(ValueError):
    """A contract or file-identity check failed."""


MAX_JSON_BYTES = 2 * 1024 * 1024
ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
ASSURANCE = "self_reported"
LIMITATION = "Gate validation covers file identity and self-reported attestations only; it does not execute or independently verify checkers, certify correctness, or validate recalculation."


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def exact_keys(value: object, keys: set[str], label: str) -> dict:
    require(type(value) is dict, f"{label} must be an object")
    require(set(value) == keys, f"{label} keys must be exactly {sorted(keys)}")
    return value


def version(value: object) -> None:
    require(type(value) is int and value == 1, "schema_version must be integer 1")


def string(value: object, label: str, limit: int = 10000) -> str:
    require(type(value) is str and 0 < len(value) <= limit, f"{label} must be a nonempty string of at most {limit} characters")
    require(value == value.strip() and not any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value), f"invalid whitespace/control character/Unicode in {label}")
    return value


def identifier(value: object, label: str) -> str:
    value = string(value, label, 100)
    require(ID.fullmatch(value) is not None, f"{label} must use lowercase kebab case")
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


def root_path(root: Path) -> Path:
    root = no_symlinks(root)
    require(root.is_dir(), "root must be an existing directory")
    return root


def relative_name(value: object) -> str:
    value = string(value, "relative path", 4096)
    require(not PurePosixPath(value).is_absolute() and "\\" not in value and ":" not in value, "path must be POSIX relative")
    require(all(part not in ("", ".", "..") for part in value.split("/")), "path contains an empty, dot, or parent component")
    return value


def relative_file(root: Path, value: object) -> Path:
    value = relative_name(value)
    target = no_symlinks(root / value)
    require(target.is_relative_to(root), "file escapes supplied root")
    require(target.is_file(), f"file is missing or not regular: {value}")
    return target


def bytes_fingerprint(data: bytes) -> dict:
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def fingerprint(path: Path) -> dict:
    path = no_symlinks(path)
    require(path.is_file(), f"file is missing or not regular: {path}")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), "target must be a regular file")
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.fstat(stream.fileno())
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "file changed while hashing")
    return {"sha256": digest, "size": after.st_size}


def load_json(path: Path) -> tuple[object, dict]:
    path = no_symlinks(path)
    require(path.is_file(), f"JSON input is not a regular file: {path}")
    require(path.stat().st_size <= MAX_JSON_BYTES, "JSON input exceeds 2 MiB")
    with path.open("rb") as stream:
        data = stream.read(MAX_JSON_BYTES + 1)
    require(len(data) <= MAX_JSON_BYTES, "JSON input exceeds 2 MiB")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValidationError(f"invalid UTF-8 JSON: {exc}") from exc
    return value, bytes_fingerprint(data)


def nonempty_list(value: object, label: str, limit: int = 1000) -> list:
    require(type(value) is list and 1 <= len(value) <= limit, f"{label} must have 1–{limit} items")
    return value


def validate_checks(checks: object, artifact_ids: set[str]) -> list:
    nonempty_list(checks, "checks")
    seen = set()
    for check in checks:
        exact_keys(check, {"id", "artifact_ids", "requirement", "kind"}, "check")
        check_id = identifier(check["id"], "check id")
        require(check_id not in seen, f"duplicate check id: {check_id}")
        seen.add(check_id)
        string(check["requirement"], "requirement")
        require(check["kind"] in ("file_check", "recalculation"), "check kind must be file_check or recalculation")
        nonempty_list(check["artifact_ids"], "check artifact_ids")
        selected = set()
        for artifact_id in check["artifact_ids"]:
            identifier(artifact_id, "artifact id")
            require(artifact_id in artifact_ids, f"unknown artifact id: {artifact_id}")
            require(artifact_id not in selected, f"duplicate check artifact id: {artifact_id}")
            selected.add(artifact_id)
    return checks


def validate_fingerprint(value: dict) -> None:
    require(type(value["sha256"]) is str and HASH.fullmatch(value["sha256"]) is not None, "sha256 must have 64 lowercase hexadecimal characters")
    require(type(value["size"]) is int and value["size"] >= 0, "size must be a nonnegative integer")


def artifact_snapshots(root: Path, definitions: object, hashed: bool) -> list[dict]:
    nonempty_list(definitions, "artifacts")
    ids, paths, physical = set(), set(), set()
    snapshots = []
    for artifact in definitions:
        keys = {"id", "path", "sha256", "size"} if hashed else {"id", "path"}
        exact_keys(artifact, keys, "artifact")
        ident = identifier(artifact["id"], "artifact id")
        require(ident not in ids, f"duplicate artifact id: {ident}")
        ids.add(ident)
        path = relative_file(root, artifact["path"])
        require(path not in paths, f"duplicate artifact path: {artifact['path']}")
        info = path.stat()
        key = (info.st_dev, info.st_ino)
        require(key not in physical, "duplicate artifact via hard link")
        paths.add(path)
        physical.add(key)
        current = fingerprint(path)
        if hashed:
            validate_fingerprint(artifact)
            require(current == {key: artifact[key] for key in ("sha256", "size")}, f"artifact changed since initialization: {artifact['path']}")
        snapshots.append({"id": ident, "path": artifact["path"], **current})
    return snapshots


def initialize(spec: object, root: Path) -> dict:
    root = root_path(root)
    exact_keys(spec, {"schema_version", "artifacts", "checks"}, "spec")
    version(spec["schema_version"])
    artifacts = artifact_snapshots(root, spec["artifacts"], hashed=False)
    checks = validate_checks(spec["checks"], {a["id"] for a in artifacts})
    covered = {ident for check in checks for ident in check["artifact_ids"]}
    require(covered == {a["id"] for a in artifacts}, "every artifact must have an explicitly required check")
    return {"schema_version": 1, "run_id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(), "root": str(root), "artifacts": artifacts, "checks": copy.deepcopy(checks)}


def validate_run(run: object, root: Path) -> dict:
    root = root_path(root)
    exact_keys(run, {"schema_version", "run_id", "created_at", "root", "artifacts", "checks"}, "run")
    version(run["schema_version"])
    string(run["run_id"], "run_id", 36)
    try:
        identity = uuid.UUID(run["run_id"])
    except ValueError as exc:
        raise ValidationError("run_id must be a canonical UUID4") from exc
    require(str(identity) == run["run_id"] and identity.version == 4, "run_id must be a canonical UUID4")
    string(run["created_at"], "created_at", 40)
    try:
        timestamp = datetime.fromisoformat(run["created_at"])
    except ValueError as exc:
        raise ValidationError("created_at must be an ISO 8601 UTC timestamp") from exc
    require(timestamp.tzinfo is not None and timestamp.utcoffset().total_seconds() == 0, "created_at must include UTC timezone")
    require(type(run["root"]) is str and run["root"] == str(root), "supplied root differs from initialized run root")
    artifact_snapshots(root, run["artifacts"], hashed=True)
    checks = validate_checks(run["checks"], {a["id"] for a in run["artifacts"]})
    require({ident for c in checks for ident in c["artifact_ids"]} == {a["id"] for a in run["artifacts"]}, "every artifact must have an explicitly required check")
    return run


def expected_artifacts(run: dict, check: dict) -> list:
    return copy.deepcopy([a for a in run["artifacts"] if a["id"] in check["artifact_ids"]])


def validate_status(status: object, check: dict) -> None:
    require(type(status) is str and status in ("pass", "fail", "not_run"), "status must be pass, fail, or not_run")
    require(not (check["kind"] == "recalculation" and status == "pass"), "recalculation pass is unsupported: this gate does not run or validate calculation engines; record not_run or an observed failure")


def evidence_snapshots(root: Path, evidence: object, status: str, artifacts: list, hashed: bool) -> list[dict]:
    require(type(evidence) is list and len(evidence) <= 100, "evidence must be a list of at most 100 files")
    paths, physical, roles = set(), set(), set()
    artifact_physical = {(p.stat().st_dev, p.stat().st_ino) for p in (relative_file(root, a["path"]) for a in artifacts)}
    snapshots = []
    for item in evidence:
        keys = {"role", "path", "sha256", "size"} if hashed else {"role", "path"}
        exact_keys(item, keys, "evidence item")
        require(type(item["role"]) is str and item["role"] in ("checker", "log", "supporting"), "evidence role must be checker, log, or supporting")
        path = relative_file(root, item["path"])
        require(path not in paths, "duplicate evidence path")
        info = path.stat()
        key = (info.st_dev, info.st_ino)
        require(key not in physical, "duplicate evidence via hard link")
        require(key not in artifact_physical, "evidence must be distinct from inspected artifacts")
        paths.add(path)
        physical.add(key)
        roles.add(item["role"])
        current = fingerprint(path)
        if hashed:
            validate_fingerprint(item)
            require(current == {key: item[key] for key in ("sha256", "size")}, f"evidence changed since record: {item['path']}")
        snapshots.append({"role": item["role"], "path": item["path"], **current})
    if status in ("pass", "fail"):
        require({"checker", "log"}.issubset(roles), "pass/fail requires distinct checker and log fingerprints")
    return snapshots


def make_record(run: dict, run_fingerprint: dict, request: object, root: Path) -> dict:
    validate_run(run, root)
    root = root_path(root)
    exact_keys(request, {"schema_version", "check_id", "status", "summary", "evidence"}, "record request")
    version(request["schema_version"])
    identifier(request["check_id"], "check_id")
    check = next((c for c in run["checks"] if c["id"] == request["check_id"]), None)
    require(check is not None, "record check_id was not explicitly required")
    validate_status(request["status"], check)
    string(request["summary"], "summary")
    evidence = evidence_snapshots(root, request["evidence"], request["status"], run["artifacts"], hashed=False)
    return {"schema_version": 1, "run_id": run["run_id"], "run_sha256": run_fingerprint["sha256"], "check_id": request["check_id"], "status": request["status"], "summary": request["summary"], "artifacts": expected_artifacts(run, check), "evidence": evidence, "assurance": ASSURANCE}


def validate_record(record: object, run: dict, run_fingerprint: dict, root: Path) -> dict:
    exact_keys(record, {"schema_version", "run_id", "run_sha256", "check_id", "status", "summary", "artifacts", "evidence", "assurance"}, "record")
    version(record["schema_version"])
    require(record["run_id"] == run["run_id"], "mixed runs: record run_id differs")
    require(record["run_sha256"] == run_fingerprint["sha256"], "record is bound to different run manifest bytes")
    identifier(record["check_id"], "check_id")
    check = next((c for c in run["checks"] if c["id"] == record["check_id"]), None)
    require(check is not None, "record check_id was not explicitly required")
    validate_status(record["status"], check)
    string(record["summary"], "summary")
    require(type(record["artifacts"]) is list and record["artifacts"] == expected_artifacts(run, check), "record artifact binding differs from required current artifacts")
    # Validate nested types as well as equality: bool and int compare equal in Python.
    artifact_snapshots(root, record["artifacts"], hashed=True)
    require(record["assurance"] == ASSURANCE, "assurance must be self_reported")
    evidence_snapshots(root, record["evidence"], record["status"], run["artifacts"], hashed=True)
    return record


def aggregate(run: dict, run_fingerprint: dict, records: list, root: Path) -> dict:
    validate_run(run, root)
    root = root_path(root)
    require(type(records) is list, "records must be a list")
    seen = {}
    for record in records:
        record = validate_record(record, run, run_fingerprint, root)
        require(record["check_id"] not in seen, f"duplicate check record: {record['check_id']}")
        seen[record["check_id"]] = record
    missing = [c["id"] for c in run["checks"] if c["id"] not in seen]
    not_run = [c["id"] for c in run["checks"] if c["id"] in seen and seen[c["id"]]["status"] == "not_run"]
    failed = [c["id"] for c in run["checks"] if c["id"] in seen and seen[c["id"]]["status"] == "fail"]
    verdict = "INCOMPLETE" if missing or not_run else "FINDINGS" if failed else "ATTESTED"
    return {"schema_version": 1, "run_id": run["run_id"], "run_sha256": run_fingerprint["sha256"], "verdict": verdict, "required_count": len(run["checks"]), "record_count": len(records), "missing_checks": missing, "not_run_checks": not_run, "failed_checks": failed, "checks": [{"id": c["id"], "requirement": c["requirement"], "kind": c["kind"], "status": seen[c["id"]]["status"] if c["id"] in seen else "missing", "summary": seen[c["id"]]["summary"] if c["id"] in seen else "No record supplied."} for c in run["checks"]], "assurance": ASSURANCE, "limitation": LIMITATION}


def write_new(path: Path, data: dict) -> None:
    path = no_symlinks(path)
    require(path.parent.is_dir(), "output parent directory must already exist")
    rendered = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(rendered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Freeze required checks and current artifact hashes in a new run")
    init.add_argument("--spec", required=True, type=Path)
    record = commands.add_parser("record", help="Fingerprint files supporting a caller-reported check")
    record.add_argument("--run", required=True, type=Path)
    record.add_argument("--request", required=True, type=Path)
    combine = commands.add_parser("aggregate", help="Rehash all artifacts/evidence and aggregate required checks")
    combine.add_argument("--run", required=True, type=Path)
    combine.add_argument("--record", action="append", default=[], type=Path)
    for command in (init, record, combine):
        command.add_argument("--root", required=True, type=Path)
        command.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            spec, _ = load_json(args.spec)
            result = initialize(spec, args.root)
        else:
            run, run_fp = load_json(args.run)
            if args.command == "record":
                request, _ = load_json(args.request)
                result = make_record(run, run_fp, request, args.root)
            else:
                loaded = [load_json(path) for path in args.record]
                result = aggregate(run, run_fp, [value for value, _ in loaded], args.root)
                result["record_files"] = [{"path": str(no_symlinks(path)), **fp} for path, (_, fp) in zip(args.record, loaded)]
        write_new(args.output, result)
        print(json.dumps({"command": args.command, "output": str(args.output), "verdict": result.get("verdict", "RECORDED"), "assurance": ASSURANCE}))
        return {"ATTESTED": 0, "FINDINGS": 1, "INCOMPLETE": 3}.get(result.get("verdict"), 0)
    except (ValidationError, OSError) as exc:
        print(json.dumps({"error": str(exc), "verdict": "INCOMPLETE", "assurance": ASSURANCE}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
