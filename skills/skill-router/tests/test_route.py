"""Behavior and rejection tests for the local catalog suggestion contract."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "route.py"
SPEC = importlib.util.spec_from_file_location("router", SCRIPT)
router = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(router)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = {"schema_version": 1, "skills": []}
        for ident, description, alias, caps in [
            ("alpha-review", "Review report claims against evidence and coverage.", "claim reviewer", ["python3.11"]),
            ("beta-audit", "Audit a workbook spreadsheet package and formulas.", "sheet audit", ["office-engine", "python3.11"]),
            ("gamma-check", "Check report evidence consistency and hashes.", "identity check", []),
        ]:
            directory = self.root / ident
            directory.mkdir()
            (directory / "SKILL.md").write_text(f"# Synthetic {ident}\n", encoding="utf-8")
            self.catalog["skills"].append({"id": ident, "path": f"{ident}/SKILL.md", "description": description, "aliases": [alias], "required_capabilities": caps})
        self.request = {"schema_version": 1, "query": "review report evidence", "available_capabilities": ["python3.11"], "limit": 3}

    def run_route(self):
        return router.route(self.catalog, self.request, self.root)

    def reviewed(self):
        self.request.update(schema_version=2,query='不要使用 beta-audit。请核对报告证据。',
                            intent={'normalized_query':'Review report evidence','excluded_skill_ids':['beta-audit'],
                                    'reviewer':'host','rationale':'Preserve the requested review and explicit exclusion.'})

    def test_reviewed_multilingual_intent_preserves_original_and_exclusion(self):
        self.reviewed();result=self.run_route()
        self.assertEqual(result['original_query'],self.request['query'])
        self.assertEqual(result['intent_assurance'],'caller_attested')
        self.assertEqual(result['suggestions'][0]['id'],'alpha-review')
        self.assertNotIn('beta-audit',[x['id'] for x in result['suggestions']])

    def test_exclusion_precedes_limit_and_capability_gap_remains(self):
        self.reviewed();self.request['limit']=1
        self.request['intent']['normalized_query']='beta-audit alpha-review'
        self.request['available_capabilities']=[]
        result=self.run_route()['suggestions'][0]
        self.assertEqual(result['id'],'alpha-review');self.assertEqual(result['missing_capabilities'],['python3.11'])

    def test_unknown_duplicate_and_malformed_intent_rejected(self):
        for exclusions in (['unknown'],['beta-audit','beta-audit']):
            self.reviewed();self.request['intent']['excluded_skill_ids']=exclusions
            with self.assertRaises(router.ValidationError):self.run_route()
        self.reviewed();self.request['intent']['confidence']=1
        with self.assertRaises(router.ValidationError):self.run_route()

    def test_all_excluded_is_valid_empty_result(self):
        self.reviewed();self.request['intent']['excluded_skill_ids']=[x['id'] for x in self.catalog['skills']]
        self.assertEqual(self.run_route()['suggestions'],[])

    def test_named_id_beats_larger_lexical_overlap(self):
        self.request["query"] = "Use beta-audit for review report claims evidence coverage"
        result = self.run_route()
        self.assertEqual(result["suggestions"][0]["id"], "beta-audit")
        self.assertEqual(result["suggestions"][0]["match_kind"], "named")
        self.assertEqual(result["suggestions"][0]["missing_capabilities"], ["office-engine"])

    def test_alias_is_case_and_separator_insensitive(self):
        self.request["query"] = "Please use SHEET_audit"
        result = self.run_route()["suggestions"][0]
        self.assertEqual(result["id"], "beta-audit")
        self.assertEqual(result["matched_names"], ["sheet audit"])

    def test_name_requires_token_boundaries(self):
        self.request["query"] = "sheet auditor"
        result = self.run_route()["suggestions"]
        self.assertTrue(all(s["match_kind"] == "lexical" for s in result))

    def test_bounded_deterministic_and_no_mutation(self):
        original = copy.deepcopy((self.catalog, self.request))
        self.request["limit"] = 1
        expected_request = copy.deepcopy(self.request)
        first = self.run_route()
        self.assertEqual(first, self.run_route())
        self.assertEqual(len(first["suggestions"]), 1)
        self.assertEqual(first["omitted_count"], 1)
        self.assertEqual(self.catalog, original[0])
        self.assertEqual(self.request, expected_request)

    def test_ties_sort_by_id_not_catalog_order(self):
        self.request["query"] = "evidence"
        self.catalog["skills"].reverse()
        self.assertEqual([s["id"] for s in self.run_route()["suggestions"]], ["alpha-review", "gamma-check"])

    def test_no_overlap_returns_empty(self):
        self.request["query"] = "photograph sunset"
        self.assertEqual(self.run_route()["suggestions"], [])

    def test_stopword_only_query_returns_empty(self):
        self.request["query"] = "please use a skill"
        self.assertEqual(self.run_route()["candidate_count"], 0)

    def test_more_specific_named_phrase_first(self):
        self.catalog["skills"][0]["aliases"] = ["audit"]
        self.request["query"] = "sheet audit"
        self.assertEqual(self.run_route()["suggestions"][0]["id"], "beta-audit")

    def test_hash_changes_with_selected_file(self):
        before = self.run_route()["suggestions"][0]["skill_sha256"]
        (self.root / "alpha-review/SKILL.md").write_text("# New instructions\n", encoding="utf-8")
        self.assertNotEqual(before, self.run_route()["suggestions"][0]["skill_sha256"])

    def test_unknown_keys_at_each_level_rejected(self):
        for where in ("catalog", "entry", "request"):
            with self.subTest(where=where):
                catalog, request = copy.deepcopy(self.catalog), copy.deepcopy(self.request)
                ({"catalog": catalog, "entry": catalog["skills"][0], "request": request}[where])["extra"] = True
                with self.assertRaises(router.ValidationError):
                    router.route(catalog, request, self.root)

    def test_wrong_types_and_limits_rejected(self):
        for key, value in [("schema_version", True), ("schema_version", 1.0), ("limit", True), ("limit", 0), ("limit", 6), ("query", ""), ("query", []), ("available_capabilities", "python3.11"), ("available_capabilities", ["python3.11", "python3.11"])]:
            with self.subTest(key=key, value=value):
                request = {**self.request, key: value}
                with self.assertRaises(router.ValidationError):
                    router.route(self.catalog, request, self.root)

    def test_catalog_wrong_types_rejected(self):
        for catalog in [[], {"schema_version": True, "skills": self.catalog["skills"]}, {"schema_version": 1, "skills": []}]:
            with self.subTest(catalog=catalog), self.assertRaises(router.ValidationError):
                router.route(catalog, self.request, self.root)

    def test_duplicate_id_and_alias_rejected(self):
        for value in ["claim reviewer", "CLAIM_REVIEWER", "alpha-review"]:
            with self.subTest(alias=value):
                catalog = copy.deepcopy(self.catalog)
                catalog["skills"][1]["aliases"] = [value]
                with self.assertRaisesRegex(router.ValidationError, "ambiguous"):
                    router.route(catalog, self.request, self.root)
        self.catalog["skills"][1]["id"] = "alpha-review"
        with self.assertRaises(router.ValidationError):
            self.run_route()

    def test_self_duplicate_alias_rejected(self):
        self.catalog["skills"][0]["aliases"].append("alpha review")
        with self.assertRaises(router.ValidationError):
            self.run_route()

    def test_unsafe_and_noncanonical_paths_rejected(self):
        for path in ["../SKILL.md", "/tmp/SKILL.md", "alpha-review/../SKILL.md", "alpha-review//SKILL.md", "./alpha-review/SKILL.md", "alpha-review\\SKILL.md", "C:/SKILL.md", "alpha-review/README.md"]:
            with self.subTest(path=path):
                catalog = copy.deepcopy(self.catalog)
                catalog["skills"][0]["path"] = path
                with self.assertRaises(router.ValidationError):
                    router.route(catalog, self.request, self.root)

    def test_missing_even_unselected_file_is_rejected(self):
        (self.root / "beta-audit/SKILL.md").unlink()
        with self.assertRaisesRegex(router.ValidationError, "missing"):
            self.run_route()

    def test_directory_in_place_of_skill_is_rejected(self):
        target = self.root / "beta-audit/SKILL.md"
        target.unlink()
        target.mkdir()
        with self.assertRaises(router.ValidationError):
            self.run_route()

    def test_symlink_leaf_and_parent_rejected(self):
        target = self.root / "beta-audit/SKILL.md"
        target.unlink()
        target.symlink_to(self.root / "alpha-review/SKILL.md")
        with self.assertRaisesRegex(router.ValidationError, "symlink"):
            self.run_route()
        target.unlink()
        target.parent.rmdir()
        target.parent.symlink_to(self.root / "alpha-review", target_is_directory=True)
        with self.assertRaisesRegex(router.ValidationError, "symlink"):
            self.run_route()

    def test_duplicate_path_rejected(self):
        self.catalog["skills"][1]["path"] = "alpha-review/SKILL.md"
        with self.assertRaisesRegex(router.ValidationError, "duplicate skill path"):
            self.run_route()

    def test_hardlink_alias_rejected(self):
        target = self.root / "beta-audit/SKILL.md"
        target.unlink()
        os.link(self.root / "alpha-review/SKILL.md", target)
        with self.assertRaisesRegex(router.ValidationError, "hard link"):
            self.run_route()

    def test_duplicate_json_keys_and_nonfinite_json_rejected(self):
        for text in ['{"schema_version":1,"schema_version":1}', '{"x":{"id":1,"id":2}}', '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{"x":']:
            with self.subTest(text=text):
                file = self.root / "invalid.json"
                file.write_text(text, encoding="utf-8")
                with self.assertRaises(router.ValidationError):
                    router.load_json(file)

    def test_refuses_output_overwrite_and_symlink(self):
        target = self.root / "input.json"
        target.write_text("preserve", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            router.write_new(target, "overwrite")
        link = self.root / "output.json"
        link.symlink_to(target)
        with self.assertRaises(router.ValidationError):
            router.write_new(link, "overwrite")
        self.assertEqual(target.read_text(), "preserve")

    def test_cli_success_and_existing_output_is_rejected(self):
        catalog, request, output = [self.root / name for name in ("catalog.json", "request.json", "result.json")]
        catalog.write_text(json.dumps(self.catalog), encoding="utf-8")
        request.write_text(json.dumps(self.request), encoding="utf-8")
        cmd = [sys.executable, str(SCRIPT), "--catalog", str(catalog), "--root", str(self.root), "--request", str(request), "--output", str(output)]
        before = (catalog.read_bytes(), request.read_bytes())
        self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
        saved = output.read_bytes()
        second = subprocess.run(cmd, capture_output=True)
        self.assertEqual(second.returncode, 2)
        self.assertEqual(saved, output.read_bytes())
        self.assertEqual(before, (catalog.read_bytes(), request.read_bytes()))
        self.assertEqual(json.loads(saved)["method"], "explicit_name_then_token_overlap")

    def test_external_demo_materializes_fixtures_and_refuses_reuse(self):
        destination = self.root / "demo"
        command = [sys.executable, str(SCRIPT.parent / "demo.py"), "--output-dir", str(destination)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        routed = json.loads((destination / "result.json").read_bytes())
        self.assertEqual(routed["suggestions"][0]["id"], "table-inspector")
        self.assertEqual(routed["suggestions"][0]["missing_capabilities"], ["office-engine"])
        self.assertEqual(len(list((destination / "catalog-root").rglob("SKILL.md"))), 3)
        self.assertEqual(list(SCRIPT.parents[1].rglob("SKILL.md")), [SCRIPT.parents[1] / "SKILL.md"])
        before = {str(p.relative_to(destination)): p.read_bytes() for p in destination.rglob("*") if p.is_file()}
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
        self.assertTrue(all((destination / name).read_bytes() == data for name, data in before.items()))

    def test_demo_refuses_destination_inside_package(self):
        destination = SCRIPT.parents[1] / "forbidden-demo-output"
        self.assertFalse(destination.exists())
        result = subprocess.run([sys.executable, str(SCRIPT.parent / "demo.py"), "--output-dir", str(destination)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside the skill package", result.stderr)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
