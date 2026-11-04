#!/usr/bin/env python3
"""Local, append-only evidence records. Structure checks do not verify source truth."""

import argparse
import copy
import datetime as dt
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

LIMIT = 8 * 1024 * 1024
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def keys(obj, expected, label):
    require(isinstance(obj, dict) and set(obj) == set(expected.split()),
            f"{label}: expected fields {expected}")


def string(value, label, empty=False):
    require(isinstance(value, str) and (empty or bool(value.strip()))
            and len(value) <= 20000, f"{label}: expected bounded text")


def identifier(value, label):
    require(isinstance(value, str) and ID.fullmatch(value), f"{label}: invalid ID")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def read_bytes(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(LIMIT + 1)
    require(len(raw) <= LIMIT, "input exceeds 8 MiB")
    return raw


def decode(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, f"duplicate JSON key: {key}")
            out[key] = value
        return out

    def nonfinite(value):
        raise Invalid(f"nonfinite JSON number: {value}")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=nonfinite)


def load(path):
    raw = read_bytes(path)
    return decode(raw), raw


def write_new(path, raw):
    """Publish a complete new file without overwriting a file or symlink."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".ledger-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, path)
    finally:
        os.unlink(temp)


def new_ledger(ledger_id):
    identifier(ledger_id, "ledger_id")
    return {"schema_version": 1, "ledger_id": ledger_id, "revision": 0,
            "parent_sha256": None, "sources": [], "claims": [], "reviews": []}


def source_check(source):
    keys(source, "source_id label version sha256 limitations", "source")
    identifier(source["source_id"], "source_id")
    for key in ("label", "version"):
        string(source[key], key)
    string(source["limitations"], "limitations", empty=True)
    require(isinstance(source["sha256"], str) and SHA.fullmatch(source["sha256"]),
            "source sha256 must identify the exact source bytes")


def claim_check(claim, sources):
    keys(claim, "claim_id entity metric period units currency basis qualifiers value evidence unknown_reason", "claim")
    identifier(claim["claim_id"], "claim_id")
    for key in ("entity", "metric", "period", "units", "basis"):
        string(claim[key], key)
    require(claim["currency"] is None or
            isinstance(claim["currency"], str) and re.fullmatch("[A-Z]{3}", claim["currency"]),
            "currency must be null or a three-letter code")
    require(isinstance(claim["qualifiers"], list), "qualifiers must be a list")
    for item in claim["qualifiers"]:
        string(item, "qualifier")
    require(len(set(claim["qualifiers"])) == len(claim["qualifiers"]), "duplicate qualifier")
    value = claim["value"]
    require(value is None or type(value) in (str, bool, int, float), "value must be a JSON scalar")
    if isinstance(value, float):
        require(math.isfinite(value), "value must be finite")
    if isinstance(value, str):
        string(value, "value")
    require(isinstance(claim["evidence"], list), "evidence must be a list")
    seen = set()
    for citation in claim["evidence"]:
        keys(citation, "source_id locator", "citation")
        require(citation["source_id"] in sources, "citation has unknown source_id")
        string(citation["locator"], "locator")
        pair = (citation["source_id"], citation["locator"])
        require(pair not in seen, "duplicate citation")
        seen.add(pair)
    if value is None:
        string(claim["unknown_reason"], "unknown_reason")
    else:
        require(claim["unknown_reason"] is None, "populated value cannot have unknown_reason")
        require(bool(claim["evidence"]), "populated claim requires source evidence")


def target(claim):
    return tuple(claim[key] for key in ("entity", "metric", "period", "basis"))


def meaning(claim):
    return encode({key: claim[key] for key in ("value", "units", "currency", "qualifiers")})


def review_check(review, claims, statuses, review_ids):
    keys(review, "review_id actor date reference proposal_sha256 decisions", "review")
    identifier(review["review_id"], "review_id")
    require(review["review_id"] not in review_ids, "duplicate review_id")
    review_ids.add(review["review_id"])
    for key in ("actor", "reference"):
        string(review[key], key)
    require(isinstance(review["date"], str), "review date must be ISO YYYY-MM-DD")
    try:
        require(dt.date.fromisoformat(review["date"]).isoformat() == review["date"], "review date must be ISO YYYY-MM-DD")
    except ValueError as error:
        raise Invalid("review date must be ISO YYYY-MM-DD") from error
    require(isinstance(review["proposal_sha256"], str) and SHA.fullmatch(review["proposal_sha256"]),
            "review must bind the exact proposal bytes")
    require(isinstance(review["decisions"], list), "decisions must be a list")
    seen = set()
    for decision in review["decisions"]:
        keys(decision, "claim_id action supersedes", "decision")
        cid = decision["claim_id"]
        require(isinstance(cid, str) and cid in claims, "decision has unknown claim_id")
        require(cid not in seen and statuses[cid] == "pending", "a decided claim cannot be rewritten")
        seen.add(cid)
        require(decision["action"] in ("accept", "reject"), "decision action must be accept or reject")
        supersedes = decision["supersedes"]
        require(isinstance(supersedes, list) and all(isinstance(x, str) for x in supersedes)
                and len(supersedes) == len(set(supersedes)), "supersedes must contain unique claim IDs")
        if decision["action"] == "reject":
            require(not supersedes, "reject cannot supersede accepted claims")
            statuses[cid] = "rejected"
            continue
        require(claims[cid]["value"] is not None, "unknown claims cannot be accepted")
        active = {old for old, status in statuses.items()
                  if status == "accepted" and target(claims[old]) == target(claims[cid])}
        require(set(supersedes) == active,
                f"accepting {cid} requires exact supersession of active claims: {sorted(active)}")
        for old in active:
            statuses[old] = "superseded"
        statuses[cid] = "accepted"


def validate(ledger):
    keys(ledger, "schema_version ledger_id revision parent_sha256 sources claims reviews", "ledger")
    require(type(ledger["schema_version"]) is int and ledger["schema_version"] == 1, "unsupported schema_version")
    identifier(ledger["ledger_id"], "ledger_id")
    require(type(ledger["revision"]) is int and ledger["revision"] >= 0, "invalid revision")
    require((ledger["revision"] == 0 and ledger["parent_sha256"] is None) or
            (ledger["revision"] > 0 and isinstance(ledger["parent_sha256"], str)
             and SHA.fullmatch(ledger["parent_sha256"])), "invalid parent_sha256")
    for key in ("sources", "claims", "reviews"):
        require(isinstance(ledger[key], list), f"{key} must be a list")
    sources, claims = {}, {}
    for source in ledger["sources"]:
        source_check(source)
        require(source["source_id"] not in sources, "duplicate source_id")
        sources[source["source_id"]] = source
    for claim in ledger["claims"]:
        claim_check(claim, sources)
        require(claim["claim_id"] not in claims, "duplicate claim_id")
        claims[claim["claim_id"]] = claim
    statuses = {cid: "pending" for cid in claims}
    review_ids = set()
    for review in ledger["reviews"]:
        review_check(review, claims, statuses, review_ids)
    require(ledger["revision"] == len(ledger["reviews"]), "revision must match review history length")
    conflicts = []
    grouped = {}
    for claim in claims.values():
        if statuses[claim["claim_id"]] in ("accepted", "pending") and claim["value"] is not None:
            grouped.setdefault(target(claim), []).append(claim)
    for group in grouped.values():
        if len({meaning(claim) for claim in group}) > 1:
            conflicts.append({"claim_ids": [claim["claim_id"] for claim in group],
                              "reason": "value_or_context_difference"})
    return {"structure": "valid", "source_truth": "not_checked", "statuses": statuses,
            "conflicts": conflicts, "unknown_claims": [cid for cid, c in claims.items() if c["value"] is None]}


def merged(ledger, update):
    validate(ledger)
    keys(update, "sources claims", "update")
    out = copy.deepcopy(ledger)
    added = {"sources": [], "claims": []}
    for plural, field in (("sources", "source_id"), ("claims", "claim_id")):
        require(isinstance(update[plural], list), f"update {plural} must be a list")
        existing = {item[field]: item for item in out[plural]}
        incoming = set()
        for item in update[plural]:
            require(isinstance(item, dict) and isinstance(item.get(field), str), f"missing {field}")
            identity = item[field]
            require(identity not in incoming, f"duplicate update {field}")
            incoming.add(identity)
            if identity in existing:
                require(encode(item) == encode(existing[identity]), f"immutable {field} changed: {identity}")
            else:
                out[plural].append(copy.deepcopy(item))
                added[plural].append(identity)
    validate(out)
    return out, added


def stage(ledger, base_raw, update):
    candidate, added = merged(ledger, update)
    return {"schema_version": 1, "ledger_id": ledger["ledger_id"],
            "base_sha256": digest(base_raw), "update": update, "added": added,
            "candidate_check": validate(candidate)}


def apply_review(ledger, base_raw, proposal, proposal_raw, review):
    keys(proposal, "schema_version ledger_id base_sha256 update added candidate_check", "proposal")
    expected = stage(ledger, base_raw, proposal["update"])
    require(encode(expected) == encode(proposal), "stale or modified proposal; stage again")
    keys(review, "review_id actor date reference proposal_sha256 decisions", "review")
    require(review["proposal_sha256"] == digest(proposal_raw), "review is bound to another proposal")
    result, _ = merged(ledger, proposal["update"])
    result["reviews"].append(copy.deepcopy(review))
    result["revision"] += 1
    result["parent_sha256"] = digest(base_raw)
    validate(result)
    return result


def markdown(ledger):
    result = validate(ledger)
    def cell(value):
        return html.escape(str(value)).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = [f"# Evidence ledger: {cell(ledger['ledger_id'])}", "",
             f"Revision: {ledger['revision']}. Source truth: not checked by this helper.", "",
             "Acceptance records a review decision; it does not prove accuracy.", "",
             "| Claim | Entity / metric / period | Value / units / currency / basis | Status | Source locators |",
             "|---|---|---|---|---|"]
    for c in ledger["claims"]:
        locations = "; ".join(f"{x['source_id']}: {x['locator']}" for x in c["evidence"])
        context = f"{c['entity']} / {c['metric']} / {c['period']}"
        value = f"{json.dumps(c['value'], ensure_ascii=False)} / {c['units']} / {c['currency'] or 'n/a'} / {c['basis']}"
        lines.append("| " + " | ".join(cell(x) for x in (c["claim_id"], context, value, result["statuses"][c["claim_id"]], locations or c["unknown_reason"])) + " |")
    lines += ["", f"Unresolved value/context differences: {len(result['conflicts'])}.", ""]
    for item in result["conflicts"]:
        lines.append("- " + " versus ".join(item["claim_ids"]))
    lines += ["", f"Unknown claims: {len(result['unknown_claims'])}.", "",
              "Read each cited span and its source version before using a claim. Qualifiers and full source hashes remain in the JSON record."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--ledger-id", required=True)
    init.add_argument("--out", required=True)
    fingerprint = sub.add_parser("fingerprint")
    fingerprint.add_argument("file")
    for name in ("validate", "report", "stage", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--ledger", required=True)
        if name != "validate":
            p.add_argument("--out", required=True)
        if name == "stage":
            p.add_argument("--input", required=True)
        if name == "apply":
            p.add_argument("--proposal", required=True)
            p.add_argument("--review", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            write_new(args.out, encode(new_ledger(args.ledger_id)))
        elif args.command == "fingerprint":
            print(digest(read_bytes(args.file)))
        else:
            ledger, raw = load(args.ledger)
            if args.command == "validate":
                print(encode(validate(ledger)).decode(), end="")
            else:
                if args.command == "report":
                    output = markdown(ledger).encode("utf-8")
                elif args.command == "stage":
                    update, _ = load(args.input)
                    output = encode(stage(ledger, raw, update))
                else:
                    proposal, proposal_raw = load(args.proposal)
                    review, _ = load(args.review)
                    output = encode(apply_review(ledger, raw, proposal, proposal_raw, review))
                require(read_bytes(args.ledger) == raw, "ledger changed during operation; retry from current version")
                write_new(args.out, output)
        return 0
    except (Invalid, OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
