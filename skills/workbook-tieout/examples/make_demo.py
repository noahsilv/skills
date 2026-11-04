#!/usr/bin/env python3
"""Create two new synthetic workbooks and an explicit comparison map."""
import argparse
import json
from pathlib import Path
from openpyxl import Workbook


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="new directory for generated example files")
    args = parser.parse_args()
    destination = Path(args.directory)
    destination.mkdir(parents=True, exist_ok=False)
    for filename, sheet, cells in [
        ("model.xlsx", "Model", {"A1": "Synthetic model, USD thousands", "A2": "Revenue FY2025", "B2": 1250,
                                 "A3": "Operating profit FY2025", "B3": 240}),
        ("source.xlsx", "Source", {"A1": "Synthetic source, USD millions", "C4": "Revenue FY2025", "D4": 1.25,
                                   "C5": "Operating profit FY2025", "D5": 0.25}),
    ]:
        wb = Workbook()
        ws = wb.active
        ws.title = sheet
        wb.properties.creator = "Synthetic example"
        for address, value in cells.items():
            ws[address] = value
        wb.save(destination / filename)
        wb.close()
    pairs = []
    for name, left, right in [("revenue", "B2", "D4"), ("operating-profit", "B3", "D5")]:
        pairs.append({"id": name, "comparison_unit": "USD thousands",
                      "left": {"sheet": "Model", "cell": left, "unit": "USD thousands", "period": "FY2025"},
                      "right": {"sheet": "Source", "cell": right, "unit": "USD millions", "period": "FY2025", "multiplier": 1000}})
    (destination / "mapping.json").write_text(json.dumps({"schema_version": 1, "pairs": pairs}, indent=2) + "\n")
    print(f"Created {destination}; expected result: FAIL, one mismatch, delta -10 USD thousands.")


if __name__ == "__main__":
    main()
