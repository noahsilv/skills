"""Check a public source tree and its skill archives against private review terms."""
import argparse
from pathlib import Path
import sys
from unicodedata import normalize
from zipfile import BadZipFile, ZipFile

from validate import DOWNLOADS, ROOT, source_files, verify_download


def folded(value):
    return normalize("NFKC", value).casefold()


def load_terms(path):
    location = path.resolve(strict=True)
    if location.is_relative_to(ROOT):
        raise ValueError("Keep the private review list outside this checkout")
    terms = {folded(line.strip()) for line in location.read_text(encoding="utf-8-sig").splitlines() if line.strip()}
    if not terms:
        raise ValueError("The private review list is empty")
    return terms


def matches(text, terms):
    text = folded(text)
    return any(term in text for term in terms)


def contains_term(path, name, terms):
    if matches(name, terms):
        return True
    if path.suffix != ".skill":
        return matches(path.read_text(encoding="utf-8"), terms)
    with ZipFile(path) as archive:
        if matches(archive.comment.decode("utf-8"), terms):
            return True
        for member in archive.infolist():
            if (matches(member.filename, terms) or matches(member.comment.decode("utf-8"), terms)
                    or matches(archive.read(member).decode("utf-8"), terms)):
                return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terms", required=True, type=Path, help="external UTF-8 file, one literal per line")
    args = parser.parse_args()
    try:
        terms = load_terms(args.terms)
        files = list(source_files())
        count = 0
        for path in files:
            name = path.relative_to(ROOT).as_posix()
            if path.suffix == ".skill":
                if name not in DOWNLOADS:
                    raise ValueError("An undeclared skill archive is present")
                verify_download(path, DOWNLOADS[name], files)
            count += int(contains_term(path, name, terms))
    except (OSError, ValueError, BadZipFile, RuntimeError):
        # Underlying errors can include the private list path or a matching filename.
        print("Check could not finish. Verify the external list, source tree and archive manifest.", file=sys.stderr)
        return 2
    print(f"Checked {len(files)} files. Files with a matching path or content: {count}.")
    return int(count != 0)


if __name__ == "__main__":
    raise SystemExit(main())
