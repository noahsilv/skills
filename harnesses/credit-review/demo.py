"""Exercise interruption, resumption and an operating-assumption revision."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


CLI = Path(__file__).with_name("run.py")


def invoke(action, root, *flags, expected=0):
    result = subprocess.run([sys.executable, str(CLI), action, str(root), *flags],
                            text=True, capture_output=True)
    if result.returncode != expected:
        raise RuntimeError(f"{action}: expected exit {expected}, got {result.returncode}. "
                           f"{result.stdout.strip()} {result.stderr.strip()}")
    return result.stdout


def states(root):
    return {row["step"]: row for row in json.loads(invoke("status", root, "--json"))}


def combined_cap(root, status):
    path = root / status["liquidity"]["folder"] / "report.json"
    report = json.loads(path.read_bytes())
    return next(c["minimum_retention_cap_from_zero"] for c in report["cases"] if c["case"] == "combined")


def revise_operations(root):
    path = root / "inputs/operations.json"
    model = json.loads(path.read_bytes())
    combined = next(c for c in model["cases"] if c["id"] == "combined")
    multipliers = combined["overrides"]["fixed_cost"]["values"]
    if multipliers != ["1.15"] * 4:
        raise ValueError("Unexpected starting assumptions for the worked revision")
    combined["overrides"]["fixed_cost"]["values"] = ["1.10"] * 4
    path.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8", newline="\n")


def walkthrough(root):
    invoke("init", root)
    invoke("advance", root, "--through", "debt")
    paused = states(root)
    invoke("verify", root, expected=1)
    invoke("advance", root)
    invoke("verify", root)
    before = states(root)
    revise_operations(root)
    changed = states(root)
    invoke("verify", root, expected=1)
    invoke("advance", root, expected=2)
    invoke("advance", root, "--refresh")
    invoke("verify", root)
    after = states(root)
    history = json.loads(invoke("history", root))
    summary = {
        "paused_after_debt": {k: s["status"] for k, s in paused.items()},
        "after_assumptions_changed": {k: s["status"] for k, s in changed.items()},
        "debt_attempt_reused": paused["debt"]["attempt"] == before["debt"]["attempt"] == after["debt"]["attempt"],
        "attempts_in_order": [r["step"] for r in history],
        "minimum_retention_cap_usd": {"original": combined_cap(root, before), "revised": combined_cap(root, after)},
        "final_verification": {k: s["status"] for k, s in after.items()},
    }
    expected = json.loads(Path(__file__).with_name("expected.json").read_bytes())
    if summary != expected:
        raise ValueError(f"Credit review differs from the worked revision: {summary}")
    rendered = json.dumps(summary, indent=2) + "\n"
    (root / "walkthrough.json").write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="a new folder for both generations and their receipts")
    args = parser.parse_args()
    try:
        if args.out is None:
            with TemporaryDirectory() as temp:
                walkthrough(Path(temp) / "credit-run")
        else:
            walkthrough(args.out)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"Credit walkthrough failed: {exc}\n")


if __name__ == "__main__":
    main()
