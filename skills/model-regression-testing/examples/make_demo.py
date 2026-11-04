#!/usr/bin/env python3
"""Generate two synthetic workbooks matching the example JSON snapshots."""
import argparse
from pathlib import Path
from openpyxl import Workbook


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="new directory")
    args = parser.parse_args()
    destination = Path(args.directory)
    destination.mkdir(parents=True, exist_ok=False)
    for filename, profit, cash in [("baseline.xlsx", 250, 420), ("current.xlsx", 240, 410)]:
        workbook = Workbook()
        workbook.properties.creator = "Synthetic example"
        sheet = workbook.active
        sheet.title = "Model"
        sheet.append(["Synthetic example — FY2025", "USD thousands"])
        sheet.append(["Operating profit", profit])
        sheet.append(["Ending cash", cash])
        sheet.append(["Balance check", True])
        workbook.save(destination / filename)
        workbook.close()
    print(f"Created {destination}. Profit and cash both change by -10; only profit is declared in changes.json.")


if __name__ == "__main__":
    main()
