"""Resume a three-step credit review and verify the files behind each receipt."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
from uuid import uuid4

from stages import CODE, FIXTURES, HERE, INPUTS, OUTPUTS, PARENT, ROOT, STEPS, sha


DB = "receipts.sqlite"


def initialize(root):
    root.mkdir(parents=True, exist_ok=False)
    (root / "inputs").mkdir()
    (root / "attempts").mkdir()
    for name, source in FIXTURES.items():
        shutil.copyfile(source, root / "inputs" / name)
    with closing(sqlite3.connect(root / DB)) as db:
        db.execute("CREATE TABLE workflow (run_id TEXT PRIMARY KEY)")
        db.execute("INSERT INTO workflow VALUES (?)", (uuid4().hex,))
        db.execute("""CREATE TABLE attempts (
            id INTEGER PRIMARY KEY, step TEXT NOT NULL, folder TEXT UNIQUE NOT NULL,
            outcome TEXT NOT NULL, inputs TEXT NOT NULL, outputs TEXT NOT NULL,
            parent_id INTEGER REFERENCES attempts(id), detail TEXT NOT NULL, runtime TEXT NOT NULL,
            recorded_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))""")
        db.execute("PRAGMA user_version = 1")
        db.commit()


def connect(root, writable=False):
    mode = "rw" if writable else "ro"
    db = sqlite3.connect((root / DB).resolve().as_uri() + "?mode=" + mode,
                         uri=True, isolation_level=None, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    if db.execute("PRAGMA user_version").fetchone()[0] != 1:
        db.close()
        raise ValueError("Unknown receipt database version")
    return db


def latest(db, step):
    return db.execute("SELECT * FROM attempts WHERE step=? ORDER BY id DESC LIMIT 1", (step,)).fetchone()


def attempt_path(root, receipt):
    folder = receipt["folder"]
    if not re.fullmatch(r"[a-f0-9]{32}", folder):
        raise ValueError("Invalid attempt folder")
    return root / "attempts" / folder


def input_hashes(root, step):
    files = {f"inputs/{name}": root / "inputs" / name for name in INPUTS[step]}
    for path in (HERE / "run.py", HERE / "stages.py", *CODE[step]):
        files[path.relative_to(ROOT).as_posix()] = path
    return {name: sha(path) for name, path in files.items()}


def output_hashes(folder, step):
    names = [*OUTPUTS[step], *(f"inputs/{name}" for name in INPUTS[step])]
    if PARENT[step]:
        names.append("upstream/report/report.json")
    return {name: sha(folder / name) for name in names}


def stage_inputs(root, folder, step, inputs, prior):
    snapshots = folder / "inputs"
    snapshots.mkdir()
    for name in INPUTS[step]:
        target = snapshots / name
        shutil.copyfile(root / "inputs" / name, target)
        if sha(target) != inputs[f"inputs/{name}"]:
            raise ValueError(f"{name} changed while the input was copied")
    if prior:
        upstream = folder / "upstream/report/report.json"
        upstream.parent.mkdir(parents=True)
        shutil.copyfile(attempt_path(root, prior) / "report/report.json", upstream)
        if sha(upstream) != json.loads(prior["outputs"])["report/report.json"]:
            raise ValueError("Upstream report changed while the input was copied")


def differences(saved, current):
    return sorted(k for k in saved.keys() | current.keys() if saved.get(k) != current.get(k))


def inspect(root, db):
    states = {}
    for step in STEPS:
        receipt = latest(db, step)
        parent = PARENT[step]
        row = {"step": step, "attempt": receipt["id"] if receipt else None,
               "folder": f"attempts/{receipt['folder']}" if receipt else None}
        states[step] = row
        if parent and states[parent]["status"] != "CURRENT":
            row.update(status="WAITING", reason=f"{parent} is {states[parent]['status']}")
            continue
        try:
            inputs = input_hashes(root, step)
        except OSError as exc:
            row.update(status="BLOCKED", reason=f"Input unavailable: {Path(exc.filename).name}")
            continue
        if receipt is None:
            row.update(status="READY", reason="No completed attempt")
        elif receipt["outcome"] == "FAILED":
            row.update(status="FAILED", reason=receipt["detail"])
        elif parent and receipt["parent_id"] != states[parent]["attempt"]:
            row.update(status="STALE", reason=f"{parent} now has a different receipt")
        else:
            changed = differences(json.loads(receipt["inputs"]), inputs)
            try:
                output_changes = differences(json.loads(receipt["outputs"]), output_hashes(attempt_path(root, receipt), step))
                changed.extend(f"attempt/{name}" for name in output_changes)
            except OSError as exc:
                changed.append(f"missing output {Path(exc.filename).name}")
            row.update(status="STALE" if changed else "CURRENT",
                       reason=", ".join(changed) if changed else "Recorded inputs and outputs match")
    return states


def record(db, step, folder, outcome, inputs, outputs, parent_id, detail):
    runtime = f"{sys.implementation.name} {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    db.execute("INSERT INTO attempts(step, folder, outcome, inputs, outputs, parent_id, detail, runtime) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
               (step, folder, outcome, json.dumps(inputs, sort_keys=True), json.dumps(outputs, sort_keys=True),
                parent_id, detail, runtime))


def advance_step(root, db, step, refresh):
    # The writer transaction spans the calculation and publication of its receipt.
    # A second writer rechecks the state under the same lock before doing any work.
    db.execute("BEGIN IMMEDIATE")
    try:
        states = inspect(root, db)
        state = states[step]
        if state["status"] == "CURRENT":
            db.commit()
            return
        if state["status"] in {"FAILED", "STALE"} and not refresh:
            raise ValueError(f"{step} is {state['status']}: {state['reason']}. Use --refresh after review.")
        if state["status"] in {"BLOCKED", "WAITING"}:
            raise ValueError(f"{step} is {state['status']}: {state['reason']}")
        inputs = input_hashes(root, step)
        parent = PARENT[step]
        prior = latest(db, parent) if parent else None
        parent_id = prior["id"] if prior else None
        token = uuid4().hex
        folder = root / "attempts" / token
        folder.mkdir()
        command = [sys.executable, "-B", str(HERE / "stages.py"), step, str(folder / "inputs"), str(folder)]
        if prior:
            command.append(str(folder / "upstream"))
        try:
            stage_inputs(root, folder, step, inputs, prior)
            process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if process.returncode:
                raise ValueError(process.stderr.strip() or f"Finance stage exited {process.returncode}")
            if input_hashes(root, step) != inputs:
                raise ValueError("Declared input changed during execution")
            if parent and inspect(root, db)[parent]["status"] != "CURRENT":
                raise ValueError("Upstream evidence changed during execution")
            outputs = output_hashes(folder, step)
            if any(outputs[f"inputs/{name}"] != inputs[f"inputs/{name}"] for name in INPUTS[step]):
                raise ValueError("Input snapshot changed during execution")
            if prior and outputs["upstream/report/report.json"] != json.loads(prior["outputs"])["report/report.json"]:
                raise ValueError("Upstream snapshot changed during execution")
        except (OSError, ValueError) as exc:
            record(db, step, token, "FAILED", inputs, {}, parent_id, str(exc))
            db.commit()
            raise
        record(db, step, token, "COMPLETED", inputs, outputs, parent_id, "")
        db.commit()
    except BaseException:
        db.rollback()
        raise


def receipts(db, step=None):
    run_id = db.execute("SELECT run_id FROM workflow").fetchone()[0]
    sql = "SELECT * FROM attempts"
    rows = db.execute(sql + " WHERE step=? ORDER BY id DESC LIMIT 1", (step,)) if step else db.execute(sql + " ORDER BY id")
    result = []
    for row in rows:
        item = {"run_id": run_id, **dict(row)}
        for field in ("inputs", "outputs"):
            item[field] = json.loads(item[field])
        result.append(item)
    return result


def show(states, as_json):
    if as_json:
        print(json.dumps(list(states.values()), indent=2))
    else:
        for row in states.values():
            label = f" (attempt {row['attempt']})" if row["attempt"] is not None else ""
            print(f"{row['step']}: {row['status']}{label} | {row['reason']}")
            if row["folder"]:
                print(f"  {row['folder']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("init", "advance", "status", "verify", "history", "receipt"):
        command = commands.add_parser(action)
        command.add_argument("directory", type=Path)
        if action in ("advance", "status", "verify"):
            command.add_argument("--json", action="store_true")
        if action == "advance":
            command.add_argument("--through", choices=STEPS, default=STEPS[-1])
            command.add_argument("--refresh", action="store_true", help="create new attempts for stale or failed work")
        if action == "receipt":
            command.add_argument("step", choices=STEPS)
    args = parser.parse_args()
    root = args.directory.resolve()
    try:
        if args.action == "init":
            initialize(root)
            print(f"Initialized {root.name}")
            return 0
        with closing(connect(root, writable=args.action == "advance")) as db:
            if args.action in ("history", "receipt"):
                rows = receipts(db, getattr(args, "step", None))
                print(json.dumps(rows, indent=2))
                return int(args.action == "receipt" and not rows)
            if args.action == "advance":
                for step in STEPS[:STEPS.index(args.through) + 1]:
                    advance_step(root, db, step, args.refresh)
            db.execute("BEGIN")
            states = inspect(root, db)
            show(states, args.json)
            if args.action == "advance":
                return int(any(states[step]["status"] != "CURRENT" for step in STEPS[:STEPS.index(args.through) + 1]))
            return int(args.action == "verify" and any(row["status"] != "CURRENT" for row in states.values()))
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(2, f"Credit review: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
