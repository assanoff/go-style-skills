#!/usr/bin/env python3
"""Scores a go-style report against the seeded problems of the eval fixture.

    python3 score.py REPORT.json [--expected expected.json] [--json]
                     [--min-lint-recall R] [--max-unexpected N]

REPORT.json is the .json twin that `gostyle.py report` writes next to the
Markdown report. Recall is computed over the expected items that belong to the
guides of the run; findings that match no item are listed for manual review
(they are false positives or problems the fixture did not mean to seed).

With --min-lint-recall or --max-unexpected the script exits with status 1 when
the score misses a threshold, so CI can check a linter-only run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def base(rule_id: str) -> str:
    return rule_id.split("/", 1)[0]


def item_lines(fixture: Path, item: dict, problems: list) -> list[int]:
    try:
        text = (fixture / item["file"]).read_text(encoding="utf-8").splitlines()
    except OSError:
        problems.append(f"{item['id']}: missing file {item['file']}")
        return []
    lines = [n for m in item["match"] for n, line in enumerate(text, 1) if m in line]
    if not lines:
        problems.append(f"{item['id']}: no line matches {item['match']}")
    return lines


def matches(f: dict, item: dict, lines: list[int]) -> bool:
    tol = item.get("tolerance", 3)
    return (f["file"] == item["file"] and base(f["rule"]) in item["rules"]
            and any(abs(f["line"] - n) <= tol for n in lines))


def score(rep: dict, exp: dict, fixture: Path) -> tuple[dict, list[dict]]:
    """Returns the score of a report and its findings that match no expected item."""
    guides = set(rep["guides"])
    findings = [f for f in rep["findings"] if f.get("verified", True)]
    unverified = [f for f in rep["findings"] if not f.get("verified", True)]

    problems: list[str] = []
    used: set[int] = set()
    rows = []
    dropped = rep.get("dropped_rules", [])
    for item in exp["items"]:
        # Rules of the run's guides, minus those the run left out because they
        # contradict a higher-priority guide.
        relevant = [r for r in item["rules"] if r.split(":", 1)[0] in guides
                    and not any(base(d) == r for d in dropped)]
        if not relevant:
            continue
        lines = item_lines(fixture, item, problems)
        hits = [i for i, f in enumerate(findings) if matches(f, item, lines)]
        used.update(hits)
        rows.append({"id": item["id"], "kind": item["kind"],
                     "optional": item.get("optional", False), "found": bool(hits),
                     "by": sorted({findings[i]["source"] for i in hits})})

    negatives = []
    for item in exp.get("negatives", []):
        lines = item_lines(fixture, item, problems)
        negatives += [f"{item['id']}: {f['rule']} at {f['file']}:{f['line']}"
                      for f in findings if matches(f, item, lines)]

    scored = [r for r in rows if not r["optional"]]
    found = [r for r in scored if r["found"]]
    by_kind = {}
    for kind in ("lint", "llm"):
        ks = [r for r in scored if r["kind"] == kind]
        by_kind[kind] = {"found": sum(r["found"] for r in ks), "expected": len(ks)}
    unexpected = [f for i, f in enumerate(findings) if i not in used]

    result = {
        "guides": sorted(guides), "recall": round(len(found) / len(scored), 3) if scored else None,
        "found": len(found), "expected": len(scored), "by_kind": by_kind,
        "missed": [r["id"] for r in scored if not r["found"]],
        "unexpected": len(unexpected), "negatives_hit": negatives,
        "unverified": len(unverified), "problems": problems,
    }
    return result, unexpected


def check(result: dict, min_lint_recall: float | None,
          max_unexpected: int | None) -> list[str]:
    """Returns one message per threshold the score misses."""
    failures = []
    if min_lint_recall is not None:
        lint = result["by_kind"]["lint"]
        if not lint["expected"]:
            failures.append("lint recall: no linter items belong to the guides of this run")
        elif lint["found"] / lint["expected"] < min_lint_recall:
            failures.append(f"lint recall {lint['found']}/{lint['expected']} "
                            f"is below {min_lint_recall}")
    if max_unexpected is not None and result["unexpected"] > max_unexpected:
        failures.append(f"{result['unexpected']} unexpected findings, "
                        f"at most {max_unexpected} allowed")
    return failures


def print_score(result: dict, unexpected: list[dict]) -> None:
    print(f"guides: {', '.join(result['guides'])}")
    print(f"recall: {result['found']}/{result['expected']} = {result['recall']}  "
          + "  ".join(f"{k} {v['found']}/{v['expected']}"
                      for k, v in result["by_kind"].items()))
    if result["missed"]:
        print("missed: " + ", ".join(result["missed"]))
    print(f"unexpected findings (review manually): {len(unexpected)}")
    for f in unexpected:
        print(f"  {f['rule']}  {f['file']}:{f['line']}  [{f['source']}] {f['message'][:110]}")
    if result["negatives_hit"]:
        print("false positives on negative items: " + "; ".join(result["negatives_hit"]))
    print(f"unverified findings: {result['unverified']}")
    if result["problems"]:
        print("fixture problems: " + "; ".join(result["problems"]), file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("report")
    ap.add_argument("--expected", default=str(Path(__file__).with_name("expected.json")))
    ap.add_argument("--json", action="store_true", help="print the score as JSON")
    ap.add_argument("--aliases", help="JSON map of alternative rule ids (heading-derived "
                    "anchors) to catalog ids, for scoring reports not made by the skills")
    ap.add_argument("--min-lint-recall", type=float, metavar="R",
                    help="fail when the share of linter items found is below R (0..1)")
    ap.add_argument("--max-unexpected", type=int, metavar="N",
                    help="fail when more than N findings match no expected item")
    args = ap.parse_args()
    if args.min_lint_recall is not None and not 0 <= args.min_lint_recall <= 1:
        ap.error("--min-lint-recall must be between 0 and 1")
    if args.max_unexpected is not None and args.max_unexpected < 0:
        ap.error("--max-unexpected must not be negative")

    exp = json.loads(Path(args.expected).read_text(encoding="utf-8"))
    fixture = Path(args.expected).parent / exp["fixture"]
    rep = json.loads(Path(args.report).read_text(encoding="utf-8"))
    if args.aliases:
        aliases = json.loads(Path(args.aliases).read_text(encoding="utf-8"))
        for f in rep["findings"]:
            f["rule"] = aliases.get(f["rule"], f["rule"])

    result, unexpected = score(rep, exp, fixture)
    if args.json:
        print(json.dumps(result, indent=1))
    else:
        print_score(result, unexpected)
    failures = check(result, args.min_lint_recall, args.max_unexpected)
    for msg in failures:
        print(f"FAIL: {msg}", file=sys.stderr)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
