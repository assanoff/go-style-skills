#!/usr/bin/env python3
"""Unit tests for the deterministic parts of go-style/scripts/gostyle.py.

    python3 evals/test_gostyle.py
"""

import argparse
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True  # keep __pycache__ out of the plugin directory
HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent / "plugins" / "go-style" / "skills" / "go-style"
SPEC = importlib.util.spec_from_file_location("gostyle", ENGINE / "scripts" / "gostyle.py")
gs = importlib.util.module_from_spec(SPEC)
sys.modules["gostyle"] = gs  # dataclasses on Python 3.9 look the module up here
SPEC.loader.exec_module(gs)


def rule(rid, conflicts=(), overlaps=(), order=0):
    guide, _, rest = rid.partition(":")
    return {"id": rid, "guide": guide, "anchor": rest.split("/", 1)[0], "order": order,
            "conflicts": list(conflicts), "overlaps": list(overlaps), "title": rid,
            "url": "u", "severity": "should", "scope": "body", "check": "llm",
            "topic": "t", "lint": [], "custom": "", "rule": ""}


class LintKeys(unittest.TestCase):
    def test_split_keeps_regex_commas(self):
        self.assertEqual(gs.split_lint_field("revive:exported~(a|b), x{1,3}y, gofmt"),
                         ["revive:exported~(a|b)", "x{1,3}y", "gofmt"])

    def test_match_check_and_regex(self):
        key = gs.parse_lint_key("revive:var-naming~^(?!don't use)")
        self.assertTrue(key.matches("revive", "var-naming", "func ParseId should be ParseID"))
        self.assertFalse(key.matches("revive", "var-naming", "don't use ALL_CAPS in Go names"))
        self.assertFalse(key.matches("revive", "receiver-naming", "x"))

    def test_issue_check_prefix(self):
        self.assertEqual(gs.issue_check("staticcheck", "ST1005: error strings should not"),
                         ("ST1005", "error strings should not"))
        self.assertEqual(gs.issue_check("errorlint", "comparing with == will fail"),
                         (None, "comparing with == will fail"))
        # "SA2002(related information): …" is not a check prefix.
        self.assertEqual(gs.issue_check("staticcheck", "SA2002(related information): x")[0],
                         None)


class Conflicts(unittest.TestCase):
    def test_either_side_and_lower_priority_loses(self):
        rules = [rule("google-guide:line-length", conflicts=["uber:avoid-overly-long-lines"]),
                 rule("uber:avoid-overly-long-lines")]
        all_guides = list(gs.GUIDES)
        self.assertEqual(gs.conflict_losers(rules, all_guides),
                         {"uber:avoid-overly-long-lines": ["google-guide:line-length"]})
        self.assertEqual(gs.conflict_losers(rules, ["uber"]), {})

    def test_section_without_rule_counts(self):
        rules = [rule("uber:error-types/constructor",
                      conflicts=["google-decisions:non-decisions"])]
        self.assertIn("uber:error-types/constructor",
                      gs.conflict_losers(rules, ["google-decisions", "uber"]))

    def test_qualified_reference_hits_one_rule(self):
        rules = [rule("effective:recover", conflicts=["uber:dont-panic/production"]),
                 rule("uber:dont-panic/production"), rule("uber:dont-panic/tests")]
        losers = gs.conflict_losers(rules, ["effective", "uber"])
        self.assertIn("uber:dont-panic/production", losers)
        self.assertNotIn("uber:dont-panic/tests", losers)


class Priority(unittest.TestCase):
    def test_one_lint_issue_folds_into_highest_guide(self):
        rules = {r["id"]: r for r in [rule("google-guide:mixed-caps"),
                                      rule("google-decisions:underscores"),
                                      rule("uber:function-names")]}
        fs = [gs.Finding("lint", "revive", rid, "a.go", 3, "don't use underscores")
              for rid in rules]
        kept, skipped = gs.apply_priority(fs, rules)
        self.assertEqual([f.rule for f in kept], ["google-guide:mixed-caps"])
        self.assertEqual(sorted(kept[0].see_also),
                         ["google-decisions:underscores", "uber:function-names"])
        self.assertFalse(skipped)

    def test_overlapping_review_findings_on_one_line(self):
        rules = {r["id"]: r for r in [
            rule("google-decisions:getters"),
            rule("effective:Getters", overlaps=["google-decisions:getters"])]}
        fs = [gs.Finding("review", "review", "google-decisions:getters", "a.go", 9, "x"),
              gs.Finding("review", "review", "effective:Getters", "a.go", 9, "y")]
        kept, _ = gs.apply_priority(fs, rules)
        self.assertEqual([f.rule for f in kept], ["google-decisions:getters"])
        self.assertEqual(kept[0].see_also, ["effective:Getters"])


class Folding(unittest.TestCase):
    def test_two_linters_one_problem_and_st1016(self):
        r = "google-practices:t-fatal-goroutine"
        rules = {r: rule(r), "google-decisions:receiver-names":
                 rule("google-decisions:receiver-names")}
        fs = [gs.Finding("lint", "staticcheck", r, "a_test.go", 45, "SA2002: …"),
              gs.Finding("lint", "govet", r, "a_test.go", 48, "testinggoroutine: …"),
              gs.Finding("lint", "revive", "google-decisions:receiver-names", "s.go", 70,
                         "receiver-naming: receiver name store is longer than 3"),
              gs.Finding("lint", "staticcheck", "google-decisions:receiver-names", "s.go",
                         89, "ST1016: methods on the same type should have the same")]
        kept = gs.fold_lint_duplicates(fs, rules)
        self.assertEqual(sorted((f.tool, f.line, f.also_lines) for f in kept),
                         [("revive", 70, []), ("staticcheck", 45, [48])])

    def test_formatter_not_folded_into_other_rule(self):
        rules = {"google-decisions:import-grouping": rule("google-decisions:import-grouping"),
                 "google-decisions:import-dot": rule("google-decisions:import-dot")}
        fs = [gs.Finding("lint", "goimports", "google-decisions:import-grouping", "m.go", 11,
                         "File is not properly formatted"),
              gs.Finding("lint", "revive", "google-decisions:import-dot", "m.go", 11,
                         "dot-imports: should not use dot imports")]
        self.assertEqual(len(gs.fold_lint_duplicates(fs, rules)), 2)

    def test_review_merged_into_nearby_lint(self):
        r = "google-practices:import-order"
        fs = [gs.Finding("lint", "goimports", r, "m.go", 11, "File is not properly formatted"),
              gs.Finding("review", "review", r, "m.go", 12, "pprof belongs in a last group",
                         fix="move it", confidence="high")]
        out = gs.merge_review_into_lint(fs)
        self.assertEqual(len(out), 1)
        self.assertIn("pprof belongs", out[0].message)
        self.assertEqual(out[0].fix, "move it")


class Verify(unittest.TestCase):
    def test_snippet_moves_line_or_fails(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.go").write_text("package a\n\nfunc (store *Store) Put() {}\n")
            cache = {}
            f = gs.Finding("review", "review", "r", "a.go", 1, "m",
                           snippet="func (store *Store) Put(")
            self.assertTrue(gs.verify_location(Path(d), f, cache))
            self.assertEqual(f.line, 3)
            g = gs.Finding("review", "review", "r", "a.go", 1, "m", snippet="not there")
            self.assertFalse(gs.verify_location(Path(d), g, cache))


class Diff(unittest.TestCase):
    def test_hunks(self):
        diff = ("diff --git a/x.go b/x.go\n--- a/x.go\n+++ b/x.go\n"
                "@@ -10,0 +11,3 @@\n+a\n+b\n+c\n@@ -20 +23 @@\n-x\n+y\n"
                "@@ -30,2 +32,0 @@\n-gone\n-gone\n")
        orig = gs.git
        try:
            def fake_git(root, *args):
                if args[0] == "rev-parse":
                    return str(root) + "\n"
                if args[0] == "diff":
                    return diff
                return ""
            gs.git = fake_git
            with tempfile.TemporaryDirectory() as d:
                got = gs.changed_lines(Path(d), "BASE")
        finally:
            gs.git = orig
        self.assertEqual(got, {"x.go": [(11, 13), (23, 23)]})


class Store(unittest.TestCase):
    """The report store is shared with go-audit, which lists it; these tests
    pin down the side of the contract written here."""

    def test_escape_module(self):
        for path, want in [("github.com/assanoff/cmd/ai", "github.com/assanoff/cmd/ai"),
                           ("github.com/BurntSushi/toml", "github.com/!burnt!sushi/toml"),
                           ("myapp", "myapp"), ("MyCompany/billing", "!my!company/billing"),
                           ("example.com/v1", "example.com/v1")]:
            self.assertEqual(gs.escape_module(path), want)
        for path in ["", "not a path", "../x", "a/../b", "a//b", "/abs", "a!b", "a.",
                     "модуль"]:
            with self.assertRaises(ValueError, msg=path):
                gs.escape_module(path)

    def test_store_dir(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"GO_STYLE_HOME": d}):
            self.assertEqual(gs.store_dir(), Path(d))
        with mock.patch.dict(os.environ, {"GO_STYLE_HOME": ""}):
            self.assertEqual(gs.store_dir(), Path.home() / ".go-style")

    def test_second_report_in_one_second(self):
        with tempfile.TemporaryDirectory() as d:
            first = gs.report_path(Path(d), "example.com/inventory", "all", "20261016-141945")
            self.assertEqual(first, Path(d, "reports", "example.com", "inventory",
                                         "20261016-141945-style-all.md"))
            first.parent.mkdir(parents=True)
            first.write_text("# report\n")
            second = gs.report_path(Path(d), "example.com/inventory", "all", "20261016-141945")
            self.assertEqual(second.name, "20261016-141945-style-all-2.md")

    def fake_run(self, d: Path) -> Path:
        """Writes a run as prepare leaves it after one reviewer task with one
        finding, linters skipped; returns its directory."""
        root = d / "src"
        root.mkdir()
        (root / "a.go").write_text("package a\n\nfunc (store *Store) Put() {}\n")
        r = next(r for r in gs.load_rules(["google-decisions"]) if r.severity == "should")
        run_dir = d / "src" / ".go-style" / "runs" / "20261016-140440-google-decisions"
        (run_dir / "findings").mkdir(parents=True)
        (run_dir / "rules.json").write_text(json.dumps([r.summary()]))
        (run_dir / "findings" / "all01.jsonl").write_text(json.dumps(
            {"rule": r.id, "file": "a.go", "line": 3, "message": "m",
             "snippet": "func (store *Store) Put("}) + "\n")
        (run_dir / "run.json").write_text(json.dumps({
            "run_id": run_dir.name, "run_dir": str(run_dir), "root": str(root),
            "module": "example.com/MyApp", "guides": ["google-decisions"], "mode": "full",
            "base": None, "targets": ["./..."], "whole_files": False, "changes": {},
            "lint": {"status": "skipped"}, "build_errors": [], "package_errors": [],
            "generated_skipped": 0, "files": 1, "lines": 3, "lint_mapped": 0,
            "lint_other_guides": {}, "lint_other_total": 0, "dropped_rules": [],
            "outline_error": None, "commit": "",
            "tasks": [{"id": "all01", "kind": "all",
                       "output": str(run_dir / "findings" / "all01.jsonl")}]}))
        return run_dir

    def report(self, run_dir: Path, output=None) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            gs.cmd_report(argparse.Namespace(run=str(run_dir), output=output))
        return out.getvalue()

    def test_report_goes_to_the_store(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d).resolve()
            run_dir = self.fake_run(d)
            store = d / "store"
            before = dt.datetime.now().astimezone().replace(microsecond=0)
            with mock.patch.dict(os.environ, {"GO_STYLE_HOME": str(store)}):
                self.report(run_dir)
            reports = sorted((store / "reports" / "example.com" / "!my!app").iterdir())
            self.assertEqual([p.suffix for p in reports], [".json", ".md"])
            self.assertRegex(reports[0].name, r"^\d{8}-\d{6}-style-google-decisions\.json$")
            rep = json.loads(reports[0].read_text())
            when = dt.datetime.fromisoformat(rep.pop("time"))
            self.assertIsNotNone(when.tzinfo, "time without a UTC offset")
            self.assertGreaterEqual(when, before)
            self.assertEqual(reports[0].name[:15], when.strftime("%Y%m%d-%H%M%S"))
            self.assertEqual({k: rep[k] for k in
                              ("format", "kind", "module", "root", "label", "total", "summary")},
                             {"format": 1, "kind": "style", "module": "example.com/MyApp",
                              "root": str(d / "src"), "label": "google-decisions", "total": 1,
                              "summary": "must 0 · should 1 · consider 0 · review 1/1 · "
                                         "linters skipped"})
            # The fields of a style report stay, for score.py among others.
            self.assertEqual(rep["guides"], ["google-decisions"])
            self.assertEqual(len(rep["findings"]), 1)
            # Runs stay in the module.
            self.assertFalse((d / "src" / ".go-style" / "reports").exists())

    def test_output_wins(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            run_dir = self.fake_run(d)
            store = d / "store"
            with mock.patch.dict(os.environ, {"GO_STYLE_HOME": str(store)}):
                self.report(run_dir, output=str(d / "out" / "r.md"))
            self.assertTrue((d / "out" / "r.md").exists())
            self.assertEqual(json.loads((d / "out" / "r.json").read_text())["kind"], "style")
            self.assertFalse(store.exists())

    def test_store_not_writable(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            run_dir = self.fake_run(d)
            (d / "file").write_text("")  # a store that is a file
            err = io.StringIO()
            with mock.patch.dict(os.environ, {"GO_STYLE_HOME": str(d / "file")}), \
                    contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
                self.report(run_dir)
            self.assertIn("cannot write the report", err.getvalue())
            self.assertIn("--output", err.getvalue())


class Catalogs(unittest.TestCase):
    def test_catalogs_parse_and_ids_unique(self):
        problems = []
        rules = gs.load_rules(None, problems)
        self.assertGreater(len(rules), 250)
        self.assertEqual(problems, [])
        ids = [r.id for r in rules]
        self.assertEqual(len(ids), len(set(ids)))
        json.dumps([r.summary() for r in rules])  # serializable for rules.json


if __name__ == "__main__":
    unittest.main(verbosity=1)
