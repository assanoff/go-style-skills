#!/usr/bin/env python3
"""Unit tests for evals/score.py.

    python3 evals/test_score.py
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the repository
HERE = Path(__file__).resolve().parent
SCORE = HERE / "score.py"
SPEC = importlib.util.spec_from_file_location("score", SCORE)
sc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sc)

SOURCE = """package a

var MAX_RETRIES = 3

func ParseId(s string) int { return 0 }

func Run() { go work() }

// Lines apart from Run, beyond the matching tolerance of 3.



var ok = 1
"""


def finding(rule, line, source="lint", verified=True):
    return {"rule": rule, "file": "a.go", "line": line, "source": source,
            "message": "m", "verified": verified}


def write_case(tmp: Path, findings, guides=("google-decisions", "uber")):
    """Writes a fixture, expected.json and a report; returns their paths."""
    (tmp / "fixture").mkdir()
    (tmp / "fixture" / "a.go").write_text(SOURCE, encoding="utf-8")
    exp = {"fixture": "fixture", "items": [
        {"id": "caps", "file": "a.go", "match": ["MAX_RETRIES"], "kind": "lint",
         "rules": ["google-decisions:underscores"]},
        {"id": "initialism", "file": "a.go", "match": ["ParseId"], "kind": "lint",
         "rules": ["google-decisions:initialisms"]},
        {"id": "goroutine", "file": "a.go", "match": ["go work()"], "kind": "llm",
         "rules": ["uber:dont-fire-and-forget-goroutines"]},
        {"id": "debatable", "file": "a.go", "match": ["go work()"], "kind": "llm",
         "rules": ["uber:avoid-mutable-globals"], "optional": True},
        {"id": "other-guide", "file": "a.go", "match": ["MAX_RETRIES"], "kind": "lint",
         "rules": ["effective:mixed-caps"]},
    ], "negatives": [
        {"id": "plain-var", "file": "a.go", "match": ["var ok"],
         "rules": ["uber:avoid-mutable-globals"]},
    ]}
    rep = {"guides": list(guides), "findings": findings}
    (tmp / "expected.json").write_text(json.dumps(exp), encoding="utf-8")
    (tmp / "report.json").write_text(json.dumps(rep), encoding="utf-8")
    return tmp / "report.json", tmp / "expected.json"


def result(found, expected, unexpected):
    return {"by_kind": {"lint": {"found": found, "expected": expected},
                        "llm": {"found": 0, "expected": 0}},
            "unexpected": unexpected}


class Check(unittest.TestCase):
    def test_thresholds_met(self):
        self.assertEqual(sc.check(result(33, 34, 0), 0.97, 0), [])

    def test_lint_recall_below(self):
        failures = sc.check(result(33, 34, 0), 1.0, None)
        self.assertEqual(len(failures), 1)
        self.assertIn("33/34", failures[0])

    def test_unexpected_over_limit(self):
        failures = sc.check(result(34, 34, 2), None, 1)
        self.assertEqual(len(failures), 1)
        self.assertIn("2 unexpected", failures[0])

    def test_both_thresholds_missed(self):
        self.assertEqual(len(sc.check(result(10, 34, 5), 0.9, 0)), 2)

    def test_no_thresholds(self):
        self.assertEqual(sc.check(result(0, 34, 99), None, None), [])

    def test_no_lint_items_fails_recall_threshold(self):
        failures = sc.check(result(0, 0, 0), 0.5, None)
        self.assertEqual(len(failures), 1)
        self.assertIn("no linter items", failures[0])


class Score(unittest.TestCase):
    def test_score(self):
        with tempfile.TemporaryDirectory() as d:
            rep, exp = write_case(Path(d), [
                finding("google-decisions:underscores", 3),           # caps
                finding("google-decisions:initialisms/acronyms", 6),  # ParseId, 1 line off
                finding("uber:avoid-mutable-globals", 13),             # negative item
                finding("google-decisions:underscores", 3, verified=False),
            ])
            res, unexpected = sc.score(json.loads(rep.read_text()), json.loads(exp.read_text()),
                                       Path(d) / "fixture")
        self.assertEqual((res["found"], res["expected"]), (2, 3))  # optional, other guide out
        self.assertEqual(res["by_kind"]["lint"], {"found": 2, "expected": 2})
        self.assertEqual(res["by_kind"]["llm"], {"found": 0, "expected": 1})
        self.assertEqual(res["missed"], ["goroutine"])
        self.assertEqual(res["unexpected"], 1)
        self.assertEqual([f["line"] for f in unexpected], [13])
        self.assertEqual(len(res["negatives_hit"]), 1)
        self.assertEqual(res["unverified"], 1)
        self.assertEqual(res["problems"], [])


class CLI(unittest.TestCase):
    def run_score(self, findings, *flags):
        with tempfile.TemporaryDirectory() as d:
            rep, exp = write_case(Path(d), findings)
            return subprocess.run([sys.executable, "-B", str(SCORE), str(rep),
                                   "--expected", str(exp), *flags],
                                  capture_output=True, text=True)

    def test_exit_codes(self):
        both = [finding("google-decisions:underscores", 3),
                finding("google-decisions:initialisms", 5)]
        one = both[:1]
        cases = [
            ("no flags", one, [], 0),
            ("recall met", both, ["--min-lint-recall", "1"], 0),
            ("recall missed", one, ["--min-lint-recall", "0.9"], 1),
            ("unexpected missed", both + [finding("uber:avoid-mutable-globals", 13)],
             ["--max-unexpected", "0"], 1),
            ("bad recall value", both, ["--min-lint-recall", "2"], 2),
        ]
        for name, findings, flags, code in cases:
            with self.subTest(name):
                res = self.run_score(findings, *flags)
                self.assertEqual(res.returncode, code, res.stderr)
                self.assertEqual("FAIL:" in res.stderr, code == 1, res.stderr)
                if code != 2:
                    self.assertIn("recall:", res.stdout)


if __name__ == "__main__":
    unittest.main()
