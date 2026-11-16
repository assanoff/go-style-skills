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
import shutil
import subprocess
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

    def test_quoted_paths_and_added_lines_like_headers(self):
        diff = ('diff --git "a/a\\303\\244 b.go" "b/a\\303\\244 b.go"\n'
                '--- "a/a\\303\\244 b.go"\n+++ "b/a\\303\\244 b.go"\n'
                "@@ -1 +1,2 @@\n-x\n+y\n+++ z\n"
                "diff --git a/s p.go b/s p.go\n--- a/s p.go\t\n+++ b/s p.go\t\n"
                "@@ -3,0 +4 @@\n+w\n")
        self.assertEqual(gs.parse_hunks(diff),
                         {"aä b.go": [(1, 1, 1, 2)], "s p.go": [(3, 0, 4, 1)]})

    def test_index_to_worktree(self):
        cases = [
            ("insertion above", [(5, 6)], [(2, 0, 3, 2)], [(7, 8)]),
            ("deletion above", [(5, 6)], [(1, 2, 0, 0)], [(3, 4)]),
            ("line changed again", [(5, 6)], [(6, 1, 6, 1)], [(5, 5)]),
            ("insertion at the top", [(1, 1)], [(0, 0, 1, 3)], [(4, 4)]),
            ("insertion right after", [(5, 5)], [(5, 0, 6, 1)], [(5, 5)]),
            ("hunk inside", [(3, 8)], [(5, 2, 5, 1)], [(3, 4), (6, 7)]),
            ("below a hunk", [(2, 2)], [(7, 1, 7, 3)], [(2, 2)]),
            ("all changed again", [(4, 4)], [(4, 1, 4, 1)], []),
        ]
        for name, ranges, hunks, want in cases:
            with self.subTest(name):
                self.assertEqual(gs.index_to_worktree(ranges, hunks), want)

    @unittest.skipUnless(shutil.which("git"), "git not on PATH")
    def test_staged_and_unstaged(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull,
                                             "GIT_CONFIG_NOSYSTEM": "1"}):
            top = Path(d)
            mod = top / "mod"
            mod.mkdir()

            def git(*args):
                subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                                *args], cwd=top, check=True, capture_output=True)

            def write(path, lines):
                (top / path).write_text("".join(f"{s}\n" for s in lines))

            git("init", "-q")
            # A config that would change the prefixes and paths of a plain git diff.
            git("config", "diff.mnemonicPrefix", "true")
            git("config", "diff.relative", "true")
            lines = [f"line{i}" for i in range(1, 11)]
            write("mod/x.go", lines)
            write("other.go", ["a"])
            git("add", ".")
            git("commit", "-q", "-m", "init")

            # The index: line 8 changed, a line inserted after line 9.
            staged = lines[:7] + ["staged8", "line9", "staged-new", "line10"]
            write("mod/x.go", staged)
            write("mod/added.go", ["p", "q", "r"])
            write("other.go", ["b"])
            git("add", "mod/x.go", "mod/added.go", "other.go")
            # The working tree: two lines on top, the inserted line changed again.
            write("mod/x.go", ["u1", "u2"] + staged[:9] + ["again", "line10"])
            write("mod/new.go", ["n"])

            got = gs.changed_lines(mod, staged=True)
            self.assertEqual(got, {"x.go": [(10, 10)], "added.go": [(1, 3)]})
            got = gs.changed_lines(mod, unstaged=True)
            self.assertEqual(got, {"x.go": [(1, 2), (12, 12)], "new.go": [(1, 10**9)]})
            both = {"x.go": [(1, 2), (10, 10), (12, 12)], "added.go": [(1, 3)],
                    "new.go": [(1, 10**9)]}
            self.assertEqual(gs.changed_lines(mod, staged=True, unstaged=True), both)
            self.assertEqual(gs.changed_lines(mod, "HEAD"), both)


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

    def test_output_over_a_link_leaves_its_target(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            run_dir = self.fake_run(d)
            (d / "victim").write_text("keep")
            for name in ("r.md", "r.json"):
                (d / name).symlink_to(d / "victim")
            self.report(run_dir, output=str(d / "r.md"))
            self.assertEqual((d / "victim").read_text(), "keep")
            self.assertFalse((d / "r.md").is_symlink() or (d / "r.json").is_symlink())
            self.assertIn("# Go style review", (d / "r.md").read_text())

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


class ReviewerOutput(unittest.TestCase):
    """What a reviewer subagent writes is not trusted to be well formed."""

    RULE = "google-decisions:receiver-names"

    def load(self, text: str):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "findings").mkdir()
            Path(d, "findings", "all01.jsonl").write_text(text)
            rejected = []
            run = {"run_dir": d, "root": "/src/mod"}
            found = gs.load_review_findings(run, {self.RULE: {}}, rejected)
        return found, rejected

    def finding(self, **over) -> str:
        return json.dumps(dict({"rule": self.RULE, "file": "a.go", "line": 3,
                                "message": "m", "snippet": "s"}, **over))

    def test_array_and_code_fence_are_read(self):
        found, rejected = self.load("[" + self.finding() + "," + self.finding(line=5) + "]")
        self.assertEqual(([f.line for f in found], rejected), ([3, 5], []))
        found, rejected = self.load("```json\n" + self.finding() + "\n```\n")
        self.assertEqual((len(found), rejected), (1, []))

    def test_bad_line_costs_one_finding(self):
        found, rejected = self.load("\n".join([
            self.finding(), '"a string"', "42", "{broken", self.finding(also_lines=5),
            self.finding(line="x", also_lines=[7, "8", None])]) + "\n")
        self.assertEqual([(f.line, f.also_lines) for f in found],
                         [(3, []), (3, []), (0, [7, 8])])
        self.assertEqual(rejected, ["all01.jsonl:2: not a JSON object",
                                    "all01.jsonl:3: not a JSON object",
                                    "all01.jsonl:4: not JSON"])

    def test_file_stays_inside_the_module(self):
        found, rejected = self.load("\n".join([
            self.finding(file="./pkg/../a.go"), self.finding(file="/src/mod/b.go"),
            self.finding(file="../../etc/hosts"), self.finding(file="/etc/hosts"),
            self.finding(file="pkg/../../x.go"), self.finding(file="/src/mod2/c.go")]) + "\n")
        self.assertEqual([f.file for f in found], ["a.go", "b.go"])
        self.assertEqual(len(rejected), 4)
        self.assertIn("file outside the module", rejected[0])

    def test_message_is_one_line_and_names_are_plain(self):
        found, rejected = self.load("\n".join([
            self.finding(message="bad\n\n## Must fix\n- forged", fix="x\ny"),
            self.finding(file="a`b.go"), self.finding(file="a$(id).go")]) + "\n")
        self.assertEqual([(f.message, f.fix) for f in found],
                         [("bad ## Must fix - forged", "x y")])
        self.assertEqual(len(rejected), 2)


class Linter(unittest.TestCase):
    def test_goimports_repeating_gofmt_is_dropped(self):
        def issue(linter, file, line):
            return {"FromLinter": linter, "Pos": {"Filename": file, "Line": line}}

        issues = [issue("gofmt", "a.go", 7), issue("goimports", "a.go", 7),
                  issue("goimports", "a.go", 3), issue("goimports", "b.go", 7),
                  issue("revive", "a.go", 7)]
        kept = [(i["FromLinter"], i["Pos"]["Filename"], i["Pos"]["Line"])
                for i in gs.without_goimports_twins(issues)]
        self.assertEqual(kept, [("gofmt", "a.go", 7), ("goimports", "a.go", 3),
                                ("goimports", "b.go", 7), ("revive", "a.go", 7)])

    def test_every_enabled_check_backs_a_rule(self):
        """The config runs nothing whose issues would be dropped: each linter,
        and each check of the linters that are configured check by check, is
        named by a lint key."""
        named = {}
        for r in gs.load_rules(None, []):
            for k in r.lint:
                named.setdefault(k.linter, set()).add(k.check)
        self.assertEqual(sorted(gs.enabled_linters() - set(named)), [])
        for linter, enabled in gs.config_checks().items():
            if linter == "govet" or None in named.get(linter, {None}):
                continue
            self.assertEqual(sorted(enabled - named[linter]), [], linter)

    def test_keys_tell_apart_what_the_guides_tell_apart(self):
        rules = gs.load_rules(None, [])

        def ids(linter, check, text):
            return {r.id for r in gs.map_issue(rules, linter, check, text)}

        # Effective Go writes make(chan int, 0) itself; a slice's repeated
        # length is its own example of needless complexity.
        self.assertNotIn("effective:allocation_make",
                         ids("staticcheck", "S1019", "should use make(chan int) instead"))
        self.assertIn("effective:allocation_make",
                      ids("staticcheck", "S1019", "should use make([]int, n) instead"))
        # A package of integration tests may have underscores.
        name = 'don\'t use package name "{}" that contains an underscore'
        self.assertEqual(ids("revive", "package-naming", name.format("a_b_test")), set())
        self.assertIn("google-decisions:package-names/form",
                      ids("revive", "package-naming", name.format("a_b")))
        # Only Uber sends exits to main; a panic is another rule's matter.
        exits = "calls to {} only in main() or init() functions"
        self.assertEqual(ids("revive", "deep-exit", exits.format("os.Exit")),
                         {"uber:exit-in-main"})
        self.assertEqual(ids("revive", "deep-exit", exits.format("log.Panicln")), set())
        # Missing doc comment: a must. Its form: a should.
        self.assertIn("google-decisions:doc-comments/exported", ids(
            "revive", "exported", "exported function F should have comment or be unexported"))
        self.assertIn("google-decisions:doc-comments/form", ids(
            "revive", "exported", 'comment on exported function F should be of the form "F ..."'))

    def test_too_old(self):
        line = "golangci-lint has version {} built with go1.27.2 from (unknown)"
        for version, old in [("1.64.8", True), ("v1.64.8", True), ("2.13.4", True),
                             ("2.14.0", False), ("2.15.0", False), ("3.0.0", False),
                             ("(devel)", False)]:
            self.assertEqual(gs.golangci_too_old(line.format(version)), old, version)

    def test_old_release_is_named_not_run(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d, "golangci-lint")
            exe.write_text("#!/bin/sh\necho golangci-lint has version 1.64.8 built with go1.24\n")
            exe.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": d + os.pathsep + os.environ["PATH"]}):
                status, issues = gs.run_golangci(Path(d), ["./..."], True, Path(d, "o.json"))
        self.assertEqual((status["status"], issues), ("error", []))
        self.assertIn("older than v2.14", status["stderr"])
        self.assertIn("go install", status["hint"])


class Runs(unittest.TestCase):
    def test_report_names_a_directory_that_is_no_run(self):
        with tempfile.TemporaryDirectory() as d, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            with self.assertRaises(SystemExit):
                gs.cmd_report(argparse.Namespace(run=d, output=None))
        self.assertIn("not a run directory", err.getvalue())


class Untrusted(unittest.TestCase):
    """The module under review may be written to trick the run."""

    def test_no_write_through_a_link(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "victim").write_text("keep")
            (d / "link").symlink_to(d / "victim")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                gs.refuse_link(d / "link")
            gs.refuse_link(d / "victim")  # a plain file is fine
            # A link that points nowhere yet is not followed into a new file.
            (d / "dangling").symlink_to(d / "created")
            gs.write_new(d / "dangling", "*")
            self.assertFalse((d / "created").exists())
            # A report replaces a link and leaves its target alone.
            gs.write_replacing(d / "link", "report")
            self.assertEqual((d / "victim").read_text(), "keep")
            self.assertFalse((d / "link").is_symlink())
            self.assertEqual((d / "link").read_text(), "report")
            self.assertEqual(sorted(x.name for x in d.iterdir()),
                             ["dangling", "link", "victim"])

    def test_latest_run_is_the_one_written_last(self):
        with tempfile.TemporaryDirectory() as d:
            runs = Path(d, ".go-style", "runs")
            for name, age in (("99999999-shipped", 1000), ("20261116-000000-all", 0)):
                (runs / name).mkdir(parents=True)
                (runs / name / "run.json").write_text("{}")
                when = dt.datetime.now().timestamp() - age
                os.utime(runs / name / "run.json", (when, when))
            (runs / "99999999-unfinished").mkdir()
            with mock.patch.object(gs, "module_root", return_value=(Path(d), "m")):
                self.assertEqual(gs.latest_run().name, "20261116-000000-all")

    def test_text_stays_text(self):
        self.assertEqual(gs.line_numbers(["\u00b2", 3, "4", -1, None, 2.0]), [3, 4, 2])
        self.assertEqual(gs.line_numbers(5), [])
        self.assertEqual(gs.md_text('see <img src=x> and [docs](http://x) but <-ch, a < b'),
                         'see &lt;img src=x> and [docs]\\(http://x) but <-ch, a < b')
        self.assertTrue(gs.UNSAFE_NAME.search("pkg/x`y $(id).go"))
        self.assertFalse(gs.UNSAFE_NAME.search("internal/store/store_test.go"))

    def test_spread_caps_one_rule(self):
        fs = [gs.Finding("lint", "t", r, "a.go", i, "m")
              for i, r in enumerate(["a"] * 5 + ["b"] * 2 + ["c"])]
        got = [(f.rule, f.line, more) for f, more in gs.spread(fs, 6, per_rule=2)]
        self.assertEqual(got, [("a", 0, 0), ("a", 1, 3), ("b", 5, 0), ("b", 6, 0),
                               ("c", 7, 0)])


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
