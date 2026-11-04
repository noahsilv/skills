#!/usr/bin/env python3
"""Local request-list roundtrips with immutable IDs and reviewable response proposals."""

import argparse
import copy
import csv
import datetime as dt
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata

LIMIT = 8 * 1024 * 1024
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
PUBLIC = ("request_id", "category", "request", "due_date", "response", "evidence_reference")
HEADERS = ("Request ID", "Category", "Request", "Due date", "Response", "Evidence reference")


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def keys(obj, expected, label):
    require(isinstance(obj, dict) and set(obj) == set(expected.split()),
            f"{label}: expected fields {expected}")


def text(value, label, empty=False):
    require(isinstance(value, str) and (empty or bool(value.strip())) and len(value) <= 20000,
            f"{label}: expected bounded text")


def identifier(value, label):
    require(isinstance(value, str) and ID.fullmatch(value), f"invalid {label}")


def date(value, label):
    require(isinstance(value, str), f"{label}: expected ISO date")
    try:
        require(dt.date.fromisoformat(value).isoformat() == value, f"{label}: expected ISO date")
    except ValueError as error:
        raise Invalid(f"{label}: expected ISO date") from error


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def read_bytes(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(LIMIT + 1)
    require(len(raw) <= LIMIT, "input exceeds 8 MiB")
    return raw


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def nonfinite(value):
        raise Invalid(f"nonfinite JSON number: {value}")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)


def load(path):
    raw = read_bytes(path)
    return decode(raw), raw


def write_new(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".tracker-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, path)
    finally:
        os.unlink(temp)


def request_check(item):
    keys(item, "request_id category request due_date response evidence_reference status private_note", "request")
    identifier(item["request_id"], "request_id")
    for key in ("category", "request"):
        text(item[key], key)
    for key in ("response", "evidence_reference", "private_note"):
        text(item[key], key, empty=True)
    if item["due_date"] != "":
        date(item["due_date"], "due_date")
    require(item["status"] in ("open", "answered", "closed"), "invalid internal status")


def validate(state):
    keys(state, "schema_version tracker_id revision parent_sha256 issued_ids requests history", "tracker")
    require(type(state["schema_version"]) is int and state["schema_version"] == 1, "unsupported schema_version")
    identifier(state["tracker_id"], "tracker_id")
    require(type(state["revision"]) is int and state["revision"] >= 0, "invalid revision")
    require((state["revision"] == 0 and state["parent_sha256"] is None) or
            (state["revision"] > 0 and isinstance(state["parent_sha256"], str)
             and SHA.fullmatch(state["parent_sha256"])), "invalid parent_sha256")
    for key in ("issued_ids", "requests", "history"):
        require(isinstance(state[key], list), f"{key} must be a list")
    for rid in state["issued_ids"]:
        identifier(rid, "issued ID")
    require(len(set(state["issued_ids"])) == len(state["issued_ids"]), "issued IDs cannot repeat")
    ids = []
    for item in state["requests"]:
        request_check(item)
        ids.append(item["request_id"])
    require(len(set(ids)) == len(ids), "duplicate request_id")
    require(set(ids) == set(state["issued_ids"]), "issued IDs cannot be deleted or renumbered")
    require(len(state["history"]) == state["revision"], "revision must match history length")
    review_ids = set()
    for event in state["history"]:
        require(isinstance(event, dict) and event.get("kind") in ("add", "response_review"), "invalid history event")
        require(isinstance(event.get("base_sha256"), str) and SHA.fullmatch(event["base_sha256"]), "history requires base hash")
        if event["kind"] == "add":
            keys(event, "kind base_sha256 request_ids", "add event")
            require(isinstance(event["request_ids"], list) and event["request_ids"], "empty add event")
            require(all(rid in state["issued_ids"] for rid in event["request_ids"]), "unknown added ID")
        else:
            keys(event, "kind base_sha256 return_sha256 proposal_sha256 review changes", "review event")
            for key in ("return_sha256", "proposal_sha256"):
                require(isinstance(event[key], str) and SHA.fullmatch(event[key]), "invalid history hash")
            review_check(event["review"], event["proposal_sha256"])
            require(event["review"]["review_id"] not in review_ids, "duplicate review_id")
            review_ids.add(event["review"]["review_id"])
            require(isinstance(event["changes"], list), "invalid changes history")
            for change in event["changes"]:
                keys(change, "request_id before after", "change history")
                require(change["request_id"] in ids, "unknown historical request_id")
                for side in ("before", "after"):
                    keys(change[side], "status response evidence_reference", "change values")
                    require(change[side]["status"] in ("open", "answered", "closed"), "invalid historical status")
                    for key in ("response", "evidence_reference"):
                        text(change[side][key], key, empty=True)
    return {"structure": "valid", "request_count": len(ids),
            "statuses": {status: sum(x["status"] == status for x in state["requests"])
                         for status in ("open", "answered", "closed")},
            "response_truth": "not_checked"}


def initialize(tracker_id, requests):
    require(isinstance(requests, list) and bool(requests), "initial requests must be a nonempty list")
    for item in requests:
        request_check(item)
        require(item["status"] == "open" and item["response"] == "" and item["evidence_reference"] == "",
                "new requests must be open with no accepted response")
    state = {"schema_version": 1, "tracker_id": tracker_id, "revision": 0,
             "parent_sha256": None, "issued_ids": [x["request_id"] for x in requests],
             "requests": copy.deepcopy(requests), "history": []}
    validate(state)
    return state


def add_requests(state, raw, requests):
    validate(state)
    initialize(state["tracker_id"], requests)
    require(not set(x["request_id"] for x in requests) & set(state["issued_ids"]), "cannot reuse an issued ID")
    new = copy.deepcopy(state)
    added = [x["request_id"] for x in requests]
    new["requests"].extend(copy.deepcopy(requests))
    new["issued_ids"].extend(added)
    new["history"].append({"kind": "add", "base_sha256": digest(raw), "request_ids": added})
    new["revision"] += 1
    new["parent_sha256"] = digest(raw)
    validate(new)
    return new


def safe_cell(value):
    """Apostrophe-prefix formula leaders, including leaders hidden by whitespace."""
    index = 0
    while index < len(value) and (value[index].isspace() or ord(value[index]) < 32
                                  or unicodedata.category(value[index]) == "Cf"):
        index += 1
    stripped = value[index:]
    if value and (ord(value[0]) < 32 or stripped.startswith(("=", "+", "-", "@"))):
        return "'" + value
    return value


def public_row(item):
    return {key: item[key] for key in PUBLIC}


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n", quoting=csv.QUOTE_ALL)
    writer.writerow(HEADERS)
    for row in rows:
        writer.writerow([safe_cell(row[key]) for key in PUBLIC])
    return stream.getvalue().encode("utf-8")


def export(state, raw, round_id, open_only=False):
    validate(state)
    identifier(round_id, "round_id")
    rows = [public_row(item) for item in state["requests"] if not open_only or item["status"] != "closed"]
    require(bool(rows), "no requests selected for export")
    data = csv_bytes(rows)
    manifest = {"schema_version": 1, "tracker_id": state["tracker_id"], "round_id": round_id,
                "base_sha256": digest(raw), "rows": rows, "export_sha256": digest(data)}
    return data, manifest


def manifest_check(state, raw, manifest):
    keys(manifest, "schema_version tracker_id round_id base_sha256 rows export_sha256", "export manifest")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1, "unsupported manifest")
    require(manifest["tracker_id"] == state["tracker_id"], "wrong tracker_id")
    identifier(manifest["round_id"], "round_id")
    require(manifest["base_sha256"] == digest(raw), "stale export; reconcile against its original tracker snapshot")
    require(isinstance(manifest["rows"], list) and manifest["rows"], "empty export manifest")
    by_id = {item["request_id"]: item for item in state["requests"]}
    seen = set()
    for row in manifest["rows"]:
        keys(row, " ".join(PUBLIC), "export row")
        rid = row["request_id"]
        require(isinstance(rid, str) and rid in by_id and rid not in seen, "unknown or duplicate exported ID")
        require(encode(row) == encode(public_row(by_id[rid])), "manifest row differs from base tracker")
        seen.add(rid)
    require(manifest["export_sha256"] == digest(csv_bytes(manifest["rows"])), "export hash mismatch")


def archive_return(raw, archive_dir):
    archive = Path(archive_dir)
    archive.mkdir(parents=True, exist_ok=True)
    name = digest(raw) + ".csv"
    destination = archive / name
    try:
        write_new(destination, raw)
    except FileExistsError:
        require(not destination.is_symlink() and read_bytes(destination) == raw, "archive digest collision or modified archive")
    return name


def reconcile(state, state_raw, manifest, returned_raw):
    validate(state)
    manifest_check(state, state_raw, manifest)
    anomalies, proposals = [], []
    expected = {item["request_id"]: item for item in manifest["rows"]}
    returned = []
    try:
        reader = csv.reader(io.StringIO(returned_raw.decode("utf-8-sig"), newline=""), strict=True)
        header = next(reader, [])
        if header != list(HEADERS):
            anomalies.append({"code": "header_mismatch", "row": 1, "request_id": "",
                              "detail": "Expected the exact six client columns; no additional columns are read."})
        else:
            for row_number, cells in enumerate(reader, 2):
                if not cells or all(cell == "" for cell in cells):
                    continue
                if len(cells) != len(HEADERS):
                    anomalies.append({"code": "column_count", "row": row_number, "request_id": "",
                                      "detail": "Row does not have six columns."})
                    continue
                row = dict(zip(PUBLIC, cells))
                baseline = expected.get(row["request_id"])
                for key, cell in row.items():
                    # Encoding may add one apostrophe to a valid 20,000-character
                    # literal. Only an exact same-ID, same-column baseline match
                    # receives that exception; never strip new input to fit.
                    unchanged_export = baseline is not None and cell == safe_cell(baseline[key])
                    require(len(cell) <= 20000 or unchanged_export,
                            "CSV cell exceeds the 20,000-character payload limit")
                returned.append((row_number, row))
    except (UnicodeError, csv.Error, Invalid) as error:
        anomalies.append({"code": "parse_error", "row": 0, "request_id": "", "detail": str(error)})
    counts = {}
    for _, row in returned:
        counts[row["request_id"]] = counts.get(row["request_id"], 0) + 1
    for row_number, row in returned:
        rid = row["request_id"]
        def flag(code, detail):
            anomalies.append({"code": code, "row": row_number, "request_id": rid, "detail": detail})
        if not rid:
            flag("missing_id", "A nonempty row has no request ID.")
            continue
        if rid not in expected:
            flag("unknown_id", "ID was not in this export; no text-based match was attempted.")
            continue
        if counts[rid] > 1:
            flag("duplicate_id", "Every row with this duplicated ID is quarantined.")
            continue
        before = expected[rid]
        edited = [key for key in PUBLIC[:4] if row[key] != safe_cell(before[key])]
        if edited:
            flag("request_fields_edited", "Changed immutable export fields: " + ", ".join(edited))
            continue
        after = {}
        for key in ("response", "evidence_reference"):
            # Preserve stored literals on an untouched roundtrip. New input stays literal.
            after[key] = before[key] if row[key] == safe_cell(before[key]) else row[key]
        prior = {key: before[key] for key in ("response", "evidence_reference")}
        if after != prior:
            proposals.append({"request_id": rid, "row": row_number, "before": prior, "after": after})
    for rid in expected:
        if rid not in counts:
            anomalies.append({"code": "missing_exported_id", "row": 0, "request_id": rid,
                              "detail": "Request is absent from the returned file; it is not closed or deleted."})
    return {"schema_version": 1, "tracker_id": state["tracker_id"], "base_sha256": digest(state_raw),
            "return_sha256": digest(returned_raw), "archive_filename": digest(returned_raw) + ".csv",
            "export_manifest": copy.deepcopy(manifest), "proposals": proposals, "anomalies": anomalies,
            "ready_for_review": not anomalies, "response_truth": "not_checked"}


def review_check(review, proposal_sha):
    keys(review, "review_id actor date reference proposal_sha256 decisions", "review")
    identifier(review["review_id"], "review_id")
    for key in ("actor", "reference"):
        text(review[key], key)
    date(review["date"], "review date")
    require(review["proposal_sha256"] == proposal_sha, "review is bound to another proposal")
    require(isinstance(review["decisions"], list), "decisions must be a list")
    ids = set()
    for decision in review["decisions"]:
        keys(decision, "request_id accept_response close", "decision")
        identifier(decision["request_id"], "request_id")
        require(decision["request_id"] not in ids, "duplicate review decision")
        ids.add(decision["request_id"])
        require(type(decision["accept_response"]) is bool and type(decision["close"]) is bool,
                "decision flags must be JSON booleans")
        require(not decision["close"] or decision["accept_response"], "closing requires explicit response acceptance")


def apply_review(state, state_raw, proposal, proposal_raw, review, returned_raw):
    keys(proposal, "schema_version tracker_id base_sha256 return_sha256 archive_filename export_manifest proposals anomalies ready_for_review response_truth", "proposal")
    expected = reconcile(state, state_raw, proposal["export_manifest"], returned_raw)
    require(encode(expected) == encode(proposal), "proposal or archived input differs; reconcile again")
    require(proposal["ready_for_review"], "resolve all return anomalies before applying responses")
    review_check(review, digest(proposal_raw))
    require(review["decisions"], "review must decide at least one response")
    require(all(event.get("review", {}).get("review_id") != review["review_id"] for event in state["history"]),
            "review_id already used")
    offered = {item["request_id"]: item for item in proposal["proposals"]}
    require(all(item["request_id"] in offered for item in review["decisions"]), "decision refers to an unproposed response")
    new = copy.deepcopy(state)
    by_id = {item["request_id"]: item for item in new["requests"]}
    changes = []
    for decision in review["decisions"]:
        if not decision["accept_response"]:
            continue
        rid = decision["request_id"]
        item = by_id[rid]
        before = {key: item[key] for key in ("status", "response", "evidence_reference")}
        item.update(offered[rid]["after"])
        supplied = bool(item["response"].strip() or item["evidence_reference"].strip())
        require(not decision["close"] or supplied, "cannot close an empty response")
        item["status"] = "closed" if decision["close"] else "answered" if supplied else "open"
        changes.append({"request_id": rid, "before": before,
                        "after": {key: item[key] for key in ("status", "response", "evidence_reference")}})
    new["history"].append({"kind": "response_review", "base_sha256": digest(state_raw),
                           "return_sha256": digest(returned_raw), "proposal_sha256": digest(proposal_raw),
                           "review": copy.deepcopy(review), "changes": changes})
    new["revision"] += 1
    new["parent_sha256"] = digest(state_raw)
    validate(new)
    return new


def markdown(proposal):
    def cell(value):
        return html.escape(str(value)).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = ["# Returned request list: proposed changes", "",
             f"Original input SHA-256: `{proposal['return_sha256']}`.", "",
             f"Ready for review: {proposal['ready_for_review']}. Response truth: not checked.", "",
             "| Request ID | Previous response | Returned response | Returned evidence reference |",
             "|---|---|---|---|"]
    for item in proposal["proposals"]:
        lines.append("| " + " | ".join(cell(value) for value in
                     (item["request_id"], item["before"]["response"], item["after"]["response"], item["after"]["evidence_reference"])) + " |")
    lines += ["", f"Anomalies: {len(proposal['anomalies'])}.", ""]
    for item in proposal["anomalies"]:
        lines.append(f"- {cell(item['code'])}: row {item['row']}, ID {cell(item['request_id']) or '(blank)'}. {cell(item['detail'])}")
    lines += ["", "The tracker has not changed. Responses and references are client statements pending review. No files have been sent."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("--tracker-id", required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    for name in ("validate", "add", "export", "reconcile", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--tracker", required=True)
        if name != "validate":
            p.add_argument("--out", required=True)
        if name == "add":
            p.add_argument("--input", required=True)
        if name == "export":
            p.add_argument("--round-id", required=True)
            p.add_argument("--manifest", required=True)
            p.add_argument("--open-only", action="store_true")
        if name == "reconcile":
            p.add_argument("--manifest", required=True)
            p.add_argument("--returned", required=True)
            p.add_argument("--report", required=True)
        if name in ("reconcile", "apply"):
            p.add_argument("--archive", required=True)
        if name == "apply":
            p.add_argument("--proposal", required=True)
            p.add_argument("--review", required=True)
    args = parser.parse_args(argv)
    try:
        # Archive bytes before state validation or CSV parsing. Oversized inputs are rejected before capture.
        returned_raw = None
        if args.command == "reconcile":
            returned_raw = read_bytes(args.returned)
            archive_return(returned_raw, args.archive)
        if args.command == "init":
            requests, _ = load(args.input)
            write_new(args.out, encode(initialize(args.tracker_id, requests)))
            return 0
        state, raw = load(args.tracker)
        validate(state)
        if args.command == "validate":
            print(encode(validate(state)).decode(), end="")
            return 0
        if args.command == "add":
            requests, _ = load(args.input)
            output = encode(add_requests(state, raw, requests))
        elif args.command == "export":
            data, manifest = export(state, raw, args.round_id, args.open_only)
            destinations = [Path(args.out).absolute(), Path(args.manifest).absolute()]
            require(destinations[0] != destinations[1] and not any(p.exists() or p.is_symlink() for p in destinations),
                    "export and manifest destinations must be separate new files")
            require(read_bytes(args.tracker) == raw, "tracker changed during export")
            write_new(args.manifest, encode(manifest))
            write_new(args.out, data)
            return 0
        elif args.command == "reconcile":
            manifest, _ = load(args.manifest)
            proposal = reconcile(state, raw, manifest, returned_raw)
            require(Path(args.out).absolute() != Path(args.report).absolute(), "proposal and report need separate paths")
            require(not any(Path(x).exists() or Path(x).is_symlink() for x in (args.out, args.report)), "outputs must be new")
            require(read_bytes(args.tracker) == raw, "tracker changed during reconciliation")
            write_new(args.out, encode(proposal))
            write_new(args.report, markdown(proposal).encode("utf-8"))
            return 1 if proposal["anomalies"] else 0
        else:
            proposal, proposal_raw = load(args.proposal)
            require(isinstance(proposal, dict) and isinstance(proposal.get("return_sha256"), str)
                    and SHA.fullmatch(proposal["return_sha256"]),
                    "invalid return hash")
            # Compute the archive filename from the digest; do not follow a path supplied in a proposal.
            archived_path = Path(args.archive) / (proposal["return_sha256"] + ".csv")
            require(not archived_path.is_symlink(), "archive input must not be a symlink")
            returned_raw = read_bytes(archived_path)
            review, _ = load(args.review)
            output = encode(apply_review(state, raw, proposal, proposal_raw, review, returned_raw))
        require(read_bytes(args.tracker) == raw, "tracker changed during operation; retry from current version")
        write_new(args.out, output)
        return 0
    except (Invalid, OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
