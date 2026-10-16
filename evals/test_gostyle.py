#!/usr/bin/env python3
"""Unit tests for the deterministic parts of go-style/scripts/gostyle.py.

    python3 evals/test_gostyle.py
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

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
