#!/usr/bin/env python3
"""Scores a go-style report against the seeded problems of the eval fixture.

    python3 score.py REPORT.json [--expected expected.json] [--json]

REPORT.json is the .json twin that `gostyle.py report` writes next to the
Markdown report. Recall is computed over the expected items that belong to the
guides of the run; findings that match no item are listed for manual review
(they are false positives or problems the fixture did not mean to seed).
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("report")
    ap.add_argument("--expected", default=str(Path(__file__).with_name("expected.json")))
    ap.add_argument("--json", action="store_true", help="print the score as JSON")
    ap.add_argument("--aliases", help="JSON map of alternative rule ids (heading-derived "
                    "anchors) to catalog ids, for scoring reports not made by the skills")
    args = ap.parse_args()

    exp = json.loads(Path(args.expected).read_text(encoding="utf-8"))
    fixture = Path(args.expected).parent / exp["fixture"]
    rep = json.loads(Path(args.report).read_text(encoding="utf-8"))
    guides = set(rep["guides"])
    if args.aliases:
        aliases = json.loads(Path(args.aliases).read_text(encoding="utf-8"))
        for f in rep["findings"]:
            f["rule"] = aliases.get(f["rule"], f["rule"])
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
        by_kind[kind] = (sum(r["found"] for r in ks), len(ks))
    unexpected = [f for i, f in enumerate(findings) if i not in used]

    result = {
        "guides": sorted(guides), "recall": round(len(found) / len(scored), 3) if scored else None,
        "found": len(found), "expected": len(scored),
        "by_kind": {k: {"found": a, "expected": b} for k, (a, b) in by_kind.items()},
        "missed": [r["id"] for r in scored if not r["found"]],
        "unexpected": len(unexpected), "negatives_hit": negatives,
        "unverified": len(unverified), "problems": problems,
    }
    if args.json:
        print(json.dumps(result, indent=1))
        return
    print(f"guides: {', '.join(sorted(guides))}")
    print(f"recall: {len(found)}/{len(scored)} = {result['recall']}  "
          + "  ".join(f"{k} {a}/{b}" for k, (a, b) in by_kind.items()))
    if result["missed"]:
        print("missed: " + ", ".join(result["missed"]))
    print(f"unexpected findings (review manually): {len(unexpected)}")
    for f in unexpected:
        print(f"  {f['rule']}  {f['file']}:{f['line']}  [{f['source']}] {f['message'][:110]}")
    if negatives:
        print("false positives on negative items: " + "; ".join(negatives))
    print(f"unverified findings: {len(unverified)}")
    if problems:
        print("fixture problems: " + "; ".join(problems), file=sys.stderr)


if __name__ == "__main__":
    main()
