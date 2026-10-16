#!/usr/bin/env python3
"""Extracts the heading anchors of a style guide source into a TSV table.

    python3 -I anchors.py google|uber|effective SOURCE > _anchors.tsv

Columns: heading level, anchor, title, source line, alias anchors. The rule
catalogs may only link to anchors listed in these tables; `gostyle.py validate`
checks that. Run it through tools/refresh-anchors after a guide changes.

The sources are downloaded documents: they are only read as text here.
"""

import html
import re
import sys


def gh_slug(title: str) -> str:
    """GitHub's heading slug: lowercase, punctuation except - and _ dropped,
    spaces turned into dashes."""
    t = re.sub(r"<[^>]+>", "", title)
    t = re.sub(r"`", "", t).strip().lower()
    t = re.sub(r"[^\w\- ]", "", t)
    return t.replace(" ", "-")


def google(path: str):
    """Google's Markdown puts explicit <a id="..."></a> lines before headings;
    several ids before one heading are aliases."""
    out, pending, in_code = [], [], False
    for n, line in enumerate(open(path, encoding="utf-8").read().split("\n"), 1):
        if line.startswith("```"):
            in_code = not in_code
        if in_code:
            continue
        m = re.match(r'\s*<a id="([^"]+)"></a>\s*$', line)
        if m:
            pending.append(m.group(1))
            continue
        h = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if h:
            title = h.group(2)
            slug = gh_slug(title)
            ids = pending or [slug]
            # Prefer the id equal to the heading slug, then the last non-TOC id.
            named = [i for i in ids if not i.startswith("TOC-")]
            best = slug if slug in ids else (named or ids)[-1]
            out.append((len(h.group(1)), best, title, n,
                        " ".join(i for i in ids if i != best)))
            pending = []
        elif line.strip():
            pending = []
    return out


def uber(path: str):
    """Uber's guide is rendered by GitHub, which derives anchors from titles."""
    out, in_code = [], False
    for n, line in enumerate(open(path, encoding="utf-8").read().split("\n"), 1):
        if line.startswith("```"):
            in_code = not in_code
        if in_code:
            continue
        h = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if h:
            out.append((len(h.group(1)), gh_slug(h.group(2)), h.group(2), n, ""))
    return out


def effective(path: str):
    """Effective Go is HTML with id attributes on its headings."""
    out = []
    text = open(path, encoding="utf-8").read()
    for m in re.finditer(r'<h([1-4])\s+id="([^"]+)"[^>]*>(.*?)</h\1>', text, flags=re.S):
        line = text.count("\n", 0, m.start()) + 1
        title = html.unescape(re.sub(r"<[^>]+>", "", m.group(3))).strip()
        out.append((int(m.group(1)), m.group(2), title, line, ""))
    return out


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("google", "uber", "effective"):
        sys.exit(__doc__)
    extract = {"google": google, "uber": uber, "effective": effective}[sys.argv[1]]
    for level, anchor, title, line, aliases in extract(sys.argv[2]):
        print(f"{level}\t{anchor}\t{title}\t{line}\t{aliases}")


if __name__ == "__main__":
    main()
