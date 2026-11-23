"""Build and verify the two published financing cases in a disposable workbook."""
from contextlib import ExitStack
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import sys
from zipfile import ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

PACKAGE = Path(__file__).resolve().parents[2] / "skills" / "financing-pro-forma"
sys.path.insert(0, str(PACKAGE / "scripts"))
import bridge

OPENING = (
    ("Total assets", "total_assets"), ("Total liabilities", "total_liabilities"),
    ("Total equity", "total_equity"), ("Cash and equivalents", "cash_and_equivalents"),
    ("Current borrowings", "debt_current"), ("Noncurrent borrowings", "debt_noncurrent"),
    ("Current leases", "leases_current"), ("Noncurrent leases", "leases_noncurrent"),
)
FLOWS = (
    ("New short-term borrowing", "draw_current"), ("New long-term borrowing", "draw_noncurrent"),
    ("Short-term debt repaid", "repay_current"), ("Long-term debt repaid", "repay_noncurrent"),
    ("Cash equity contribution", "equity_contribution"), ("Capital spending", "capital_spending"),
    ("Cash expense", "cash_expense"),
)
# Each formula refers to the inputs or to an earlier bridge line in the same case.
LINES = (
    ("New funding", "=Inputs!{c}12+Inputs!{c}13+Inputs!{c}16", "new_funding"),
    ("Transaction uses", "=SUM(Inputs!{c}14:{c}15)+SUM(Inputs!{c}17:{c}18)", "transaction_uses"),
    ("Change in cash", "={c}2-{c}3", "change_in_cash"),
    ("Closing cash", "=Inputs!{c}5+{c}4", "cash_and_equivalents"),
    ("Total assets", "=Inputs!{c}2+{c}4+Inputs!{c}17", "total_assets"),
    ("Total liabilities", "=Inputs!{c}3+SUM(Inputs!{c}12:{c}13)-SUM(Inputs!{c}14:{c}15)", "total_liabilities"),
    ("Total equity", "=Inputs!{c}4+Inputs!{c}16-Inputs!{c}18", "total_equity"),
    ("Balance sheet difference", "={c}6-{c}7-{c}8", "balance_difference"),
    ("Gross debt including leases", "=SUM(Inputs!{c}6:{c}9)+SUM(Inputs!{c}12:{c}13)-SUM(Inputs!{c}14:{c}15)", "gross_debt_including_leases"),
    ("Net debt including leases", "={c}10-{c}5", "net_debt_including_leases"),
    ("Change in net debt", "={c}11-(SUM(Inputs!{c}6:{c}9)-Inputs!{c}5)", "change_in_net_debt"),
)

def inputs(version):
    opening, _ = bridge.read(PACKAGE / "examples" / "opening.json")
    proposals, _ = bridge.read(PACKAGE / "examples" / "transactions.json")
    if version == "challenge":
        proposals["cases"][1]["flows"]["capital_spending"] = "110"
    elif version != "baseline":
        raise ValueError("Unknown fixture version")
    return opening, proposals


def build(version):
    opening, proposals = inputs(version)
    book = Workbook()
    book.properties.creator = "Noah Silverman"
    book.properties.lastModifiedBy = "Noah Silverman"
    source = book.active
    source.title = "Inputs"
    result = book.create_sheet("Bridge")
    for sheet in book:
        sheet.append(["USD millions", "Refinancing", "Capital spending"])
        sheet.freeze_panes = "B2"
        sheet.column_dimensions["A"].width = 32
        for column in ("B", "C"):
            sheet.column_dimensions[column].width = 21
        for cell in sheet[1]:
            cell.fill = PatternFill("solid", fgColor="17324D")
            cell.font = Font(name="Calibri", color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="left")
    for label, key in OPENING:
        value = int(opening["balances"][key])
        source.append([label, value, value])
    source["A11"] = "Transaction at close"
    for label, key in FLOWS:
        source.append([label, *(int(case["flows"][key]) for case in proposals["cases"])])
    for label, formula, _ in LINES:
        result.append([label, *(formula.format(c=column) for column in ("B", "C"))])
    for sheet in book:
        for row in sheet.iter_rows(min_row=2, min_col=2):
            for cell in row:
                if cell.value is not None:
                    cell.number_format = '#,##0;[Red](#,##0);0'
                    cell.font = Font(name="Calibri", color="17528A" if sheet == source else "202020")
    return book


def snapshot(book):
    return {sheet.title: {c.coordinate: c.value for row in sheet for c in row if c.value is not None}
            for sheet in book}


def prepare(path, version):
    book = build(version)
    try:
        with BytesIO() as buffer:
            book.save(buffer)
            with ZipFile(buffer) as parts:
                # A newly authored formula has no saved value. Omit the empty
                # numeric value element emitted by openpyxl on the bridge tab.
                sheet = "xl/worksheets/sheet2.xml"
                original = parts.read(sheet)
                if original.count(b"<v></v>") != 2 * len(LINES):
                    raise ValueError("Unexpected formula-cache structure in the generated fixture")
                pending = original.replace(b"<v></v>", b"")
                with path.open("xb") as output, ZipFile(output, "w") as archive:
                    for part in parts.infolist():
                        archive.writestr(part, pending if part.filename == sheet else parts.read(part))
    finally:
        book.close()


def verify(path, version):
    opening, proposals = inputs(version)
    cases = bridge.calculate(opening, proposals)["cases"]
    with ExitStack() as stack:
        reference = build(version)
        stack.callback(reference.close)
        formulas = load_workbook(path)
        stack.callback(formulas.close)
        if snapshot(formulas) != snapshot(reference):
            raise ValueError("Saved inputs, labels or formulas differ from the named fixture")
        cached = load_workbook(path, data_only=True)
        stack.callback(cached.close)
        missing = []
        results = {}
        for column, case in zip(("B", "C"), cases, strict=True):
            expected = {**case, **case["closing_balances"], **case["closing_metrics"], "balance_difference": 0}
            values = {}
            for row, (_, _, key) in enumerate(LINES, 2):
                address = f"{column}{row}"
                value = cached["Bridge"][address].value
                if value is None:
                    missing.append(address)
                elif type(value) not in (int, float) or Decimal(str(value)) != Decimal(str(expected[key])):
                    raise ValueError(f"Cached result differs from the independent financing bridge at {address}")
                else:
                    values[key] = value
            results[case["id"]] = values
    return {"version": version, "status": "INCOMPLETE" if missing else "VERIFIED",
            "formula_count": len(LINES) * 2, "missing_caches": missing, "cases": results}
