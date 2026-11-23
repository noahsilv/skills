"""Check saved Excel formula results against a separate financing calculation."""
import argparse
import json
from pathlib import Path
import subprocess

from recalculate import calculate
from workbook import prepare, verify

VERSIONS = ("baseline", "challenge")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for command in ("prepare", "verify"):
        sub = commands.add_parser(command)
        sub.add_argument("version", choices=VERSIONS)
        sub.add_argument("path", type=Path)
    commands.add_parser("calculate", help="run both versions with installed LibreOffice Calc")
    args = parser.parse_args()
    try:
        if args.action == "calculate":
            result = calculate()
        else:
            if args.action == "prepare":
                prepare(args.path, args.version)
            result = verify(args.path, args.version)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, indent=2))
    return 2 if args.action == "verify" and result["status"] == "INCOMPLETE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
