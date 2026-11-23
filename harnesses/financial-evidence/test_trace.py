import copy
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from evidence_graph import FILES, build, impact, related, verified
from run import SOURCE_ID, calculate_version, version


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.original = Path(cls.temp.name) / "original"
        cls.revised = Path(cls.temp.name) / "revised"
        cls.first = version(cls.original, False)
        cls.second = version(cls.revised, True)

    def inputs(self, folder, source):
        for name in ("normalized", "transactions", "disclosure"):
            shutil.copyfile(source / FILES[name], folder / FILES[name])

    def test_receipt_traces_a_closing_amount_to_disclosure_and_terms(self):
        found = related(self.first, "refinance.closing.net_debt", "upstream")
        self.assertIn("reported.debt_current", found)
        self.assertIn("reported.cash_and_equivalents", found)
        self.assertIn("refinance.flow.cash_expense", found)
        self.assertNotIn("capital_spending.flow.cash_expense", found)
        node = self.first["nodes"][SOURCE_ID]
        self.assertEqual((node["value"], node["unit"]), ("90000", "USD thousands"))
        self.assertIn("physical text page 2", node["locator"])

    def test_affected_and_changed_values_are_distinct(self):
        rows = {row["id"]: row for row in impact(self.first, self.second, SOURCE_ID)}
        self.assertEqual((rows["refinance.closing.net_debt"]["original"], rows["refinance.closing.net_debt"]["revised"]), ("302", "307"))
        self.assertFalse(rows["refinance.change_in_net_debt"]["value_changed"])
        self.assertEqual(rows["refinance.change_in_net_debt"]["changed_upstream_inputs"], [SOURCE_ID])
        self.assertNotIn("refinance.closing.cash_and_equivalents", rows)

    def test_a_second_changed_input_is_visible(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            self.inputs(folder, self.revised)
            path = folder / FILES["transactions"]
            terms = json.loads(path.read_bytes())
            terms["cases"][0]["flows"]["cash_expense"] = "3"
            path.write_text(json.dumps(terms), encoding="utf-8")
            third = calculate_version(folder)
            rows = {r["id"]: r for r in impact(self.first, third, SOURCE_ID)}
            self.assertEqual(rows["refinance.closing.net_debt"]["revised"], "308")
            self.assertEqual(set(rows["refinance.closing.net_debt"]["changed_upstream_inputs"]),
                             {SOURCE_ID, "refinance.flow.cash_expense"})

    def test_rehashed_disclosure_with_wrong_quote_still_fails(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            self.inputs(folder, self.original)
            path = folder / FILES["disclosure"]
            changed = path.read_bytes().replace(b"Current borrowings excluding leases 90,000",
                                                b"Current borrowings excluding leases 91,000")
            path.write_bytes(changed)
            normalized = folder / FILES["normalized"]
            data = json.loads(normalized.read_bytes())
            data["sources"][0]["sha256"] = hashlib.sha256(changed).hexdigest()
            normalized.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "excerpt missing or ambiguous"):
                calculate_version(folder)

    def test_wrong_normalized_scale_is_recomputed(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            self.inputs(folder, self.original)
            path = folder / FILES["normalized"]
            data = json.loads(path.read_bytes())
            data["periods"][0]["values"]["leases_current"]["value"] = "1.5"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "recomputed 15"):
                calculate_version(folder)

    def test_changed_closing_metrics_disagree_with_recorded_inputs(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp) / "copy"
            shutil.copytree(self.original, folder)
            path = folder / FILES["closing"]
            data = json.loads(path.read_bytes())
            data["cases"][0]["closing_metrics"]["net_debt_including_leases"] = "300"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "recomputed 302"):
                build(folder)

    def test_edited_graph_or_source_fails_verification(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp) / "copy"
            shutil.copytree(self.original, folder)
            graph = folder / "graph.json"
            data = json.loads(graph.read_bytes())
            data["nodes"][SOURCE_ID]["value"] = "0"
            graph.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Recorded trace differs"):
                verified(folder)
            doc = folder / FILES["disclosure"]
            doc.write_bytes(doc.read_bytes() + b"Changed source version\n")
            with self.assertRaisesRegex(ValueError, "Disclosure version differs"):
                verified(folder)

    def test_query_checks_scope_nodes_and_definitions(self):
        with self.assertRaisesRegex(ValueError, "Unknown trace ID"):
            related(self.first, "missing", "upstream")
        with self.assertRaisesRegex(ValueError, "different reporting bases"):
            impact(self.first, {**self.second, "scope": "standalone"}, SOURCE_ID)
        changed = copy.deepcopy(self.second)
        changed["nodes"][SOURCE_ID]["unit"] = "USD millions"
        with self.assertRaisesRegex(ValueError, "Definition or unit changed"):
            impact(self.first, changed, SOURCE_ID)


if __name__ == "__main__":
    unittest.main()
