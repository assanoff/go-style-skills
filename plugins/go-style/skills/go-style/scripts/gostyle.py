#!/usr/bin/env python3
"""gostyle: the deterministic half of the go-style review skills.

The skills split a style review into what tools can decide and what needs
judgement. This script does the first part and the bookkeeping around the
second:

  prepare   resolve the scope (whole module, packages, or a git diff), run
            golangci-lint and map its issues to guide rules, build the
            declaration outline, the rule bundles and one task file per
            reviewer subagent
  report    merge linter issues and reviewer findings, verify every location,
            drop duplicates, apply the guide priority, render the report
  validate  check the rule catalogs (for maintainers)
  coverage  print the coverage matrix of the catalogs as Markdown

Only the Python standard library is used. Rule catalogs live in ../rules, the
golangci-lint config in ../config, the reviewer instructions in ../agents.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
RULES_DIR = ENGINE / "rules"
CONFIG = ENGINE / "config" / "golangci.yml"
REVIEWER = ENGINE / "agents" / "reviewer.md"
OUTLINE_GO = ENGINE / "scripts" / "outline.go"


@dataclasses.dataclass(frozen=True)
class Guide:
    key: str
    name: str
    short: str
    base: str
    priority: int  # lower wins


GUIDES = {
    g.key: g
    for g in [
        Guide("google-guide", "Google Go Style Guide", "Google Guide",
              "https://google.github.io/styleguide/go/guide#", 0),
        Guide("google-decisions", "Google Go Style Decisions", "Google Decisions",
              "https://google.github.io/styleguide/go/decisions#", 1),
        Guide("google-practices", "Google Go Style Best Practices",
              "Google Best Practices",
              "https://google.github.io/styleguide/go/best-practices#", 2),
        Guide("effective", "Effective Go", "Effective Go",
              "https://go.dev/doc/effective_go#", 3),
        Guide("uber", "Uber Go Style Guide", "Uber",
              "https://github.com/uber-go/guide/blob/master/style.md#", 4),
    ]
}

SEVERITIES = ("must", "should", "consider")
SCOPES = ("decl", "body", "test", "repo")
CHECKS = ("lint", "llm", "lint+llm")

# Linters whose issue text starts with "check: ", the check being a revive rule,
# a staticcheck or gosec code, a gocritic checker or a govet analyzer.
PREFIXED_LINTERS = {"revive", "staticcheck", "gocritic", "govet", "gosec", "modernize",
                    "perfsprint"}

# Defaults for splitting the review between subagents. A subagent reads one
# rule bundle and one chunk of code, so both are kept to a size it can hold
# with room to think.
SINGLE_TASK_LINES = 1500      # scope small enough for one reviewer
CHUNK_LINES = 2500            # source lines per reviewer task
BUNDLE_SPLIT_CHARS = 70_000   # split a rule bundle above this size
TASK_BUNDLE_CHARS = 90_000    # rules one small-scope task may read (~22k tokens)
OUTLINE_PART_CHARS = 110_000  # split the outline above this size


def die(msg: str) -> None:
    print(f"gostyle: {msg}", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------
# Rule catalogs


@dataclasses.dataclass
class LintKey:
    raw: str
    linter: str
    check: str | None
    regex: re.Pattern | None

    def matches(self, linter: str, check: str | None, text: str) -> bool:
        if linter != self.linter:
            return False
        if self.check is not None and self.check != check:
            return False
        return self.regex is None or bool(self.regex.search(text))


@dataclasses.dataclass
class Rule:
    id: str
    guide: str
    anchor: str
    title: str
    topic: str
    topic_file: str
    order: int
    meta: dict
    bullets: dict
    block: str
    lint: list = dataclasses.field(default_factory=list)

    @property
    def url(self) -> str:
        return GUIDES[self.guide].base + self.anchor

    @property
    def base_id(self) -> str:
        return f"{self.guide}:{self.anchor}"

    def meta_list(self, key: str) -> list[str]:
        return [v.strip() for v in self.meta.get(key, "").split(",") if v.strip()]

    @property
    def severity(self) -> str:
        return self.meta.get("severity", "")

    @property
    def scope(self) -> str:
        return self.meta.get("scope", "")

    @property
    def check(self) -> str:
        return self.meta.get("check", "")

    def summary(self) -> dict:
        return {
            "id": self.id, "guide": self.guide, "anchor": self.anchor,
            "title": self.title, "topic": self.topic, "order": self.order,
            "url": self.url, "severity": self.severity, "scope": self.scope,
            "check": self.check, "lint": [k.raw for k in self.lint],
            "custom": self.meta.get("custom", ""),
            "overlaps": self.meta_list("overlaps"),
            "conflicts": self.meta_list("conflicts"),
            "rule": self.bullets.get("rule", ""),
        }


HEADING_RE = re.compile(
    r"^### (?P<id>(?P<guide>[a-z-]+):(?P<anchor>[^\s/]+)(?:/[^\s]+)?) — (?P<title>.+?)\s*$")
META_RE = re.compile(r"^- \*\*meta:\*\*\s*(?P<meta>.+?)\s*$")
BULLET_RE = re.compile(r"^- \*\*(?P<name>[a-z ]+):\*\*\s*(?P<text>.*)$")


def parse_lint_key(raw: str) -> LintKey:
    head, _, rx = raw.partition("~")
    linter, _, check = head.partition(":")
    return LintKey(raw=raw, linter=linter.strip(), check=check.strip() or None,
                   regex=re.compile(rx) if rx else None)


def split_lint_field(value: str) -> list[str]:
    """Splits the lint= value on commas outside brackets, so that a regex such
    as x{1,3} stays in one key."""
    keys, cur, depth = [], "", 0
    for ch in value:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            keys.append(cur.strip())
            cur = ""
            continue
        cur += ch
    keys.append(cur.strip())
    return [k for k in keys if k]


def anchor_tables() -> dict[str, dict[str, int]]:
    """Returns guide -> anchor -> source line, from the _anchors.tsv files."""
    tables = {}
    for g in GUIDES:
        path = RULES_DIR / g / "_anchors.tsv"
        table = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                cols = line.split("\t")
                if len(cols) >= 4:
                    table[cols[1]] = int(cols[3])
                    for alias in (cols[4].split() if len(cols) > 4 else []):
                        table.setdefault(alias, int(cols[3]))
        tables[g] = table
    return tables


def load_rules(guides: list[str] | None = None, problems: list | None = None) -> list[Rule]:
    """Parses the topic files of the given guides, in guide order.

    Problems are appended to the problems list when it is given (validate
    mode); otherwise malformed blocks are skipped silently.
    """
    anchors = anchor_tables()
    rules: list[Rule] = []
    for g in guides or list(GUIDES):
        gdir = RULES_DIR / g
        if not gdir.is_dir():
            continue
        topic_files = []
        for path in sorted(gdir.glob("*.md")):
            if path.name.startswith("_"):
                continue
            parsed = parse_topic_file(path, g, problems)
            if parsed[1]:
                first = parsed[1][0]
                topic_files.append((anchors[g].get(first.anchor, 10**9), path, parsed))
        topic_files.sort(key=lambda t: (t[0], t[1].name))
        for _, _, (topic, file_rules) in topic_files:
            for r in file_rules:
                r.topic = topic
                r.order = len(rules)
                rules.append(r)
    return rules


def parse_topic_file(path: Path, guide: str, problems: list | None):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    topic = path.stem.replace("-", " ").capitalize()
    for line in lines:
        if line.startswith("# "):
            topic = line[2:].split(" — ")[-1].strip()
            break
    blocks, cur = [], None
    for line in lines:
        if line.startswith("### "):
            cur = [line]
            blocks.append(cur)
        elif line.startswith("## ") or line.startswith("# "):
            cur = None
        elif cur is not None:
            cur.append(line)
    rules = []
    for block in blocks:
        rule = parse_block(block, guide, path, problems)
        if rule:
            rules.append(rule)
    return topic, rules


def parse_block(block: list[str], guide: str, path: Path, problems: list | None):
    def problem(msg):
        if problems is not None:
            problems.append(f"{path.relative_to(ENGINE)}: {block[0][:70]}: {msg}")

    m = HEADING_RE.match(block[0])
    if not m:
        problem("heading is not '### <guide>:<anchor> — <title>'")
        return None
    if m["guide"] != guide:
        problem(f"rule of guide {m['guide']} in the {guide} directory")
        return None
    meta, bullets, last = {}, {}, None
    for line in block[1:]:
        mm = META_RE.match(line)
        if mm:
            for part in mm["meta"].split(" · "):
                k, _, v = part.partition("=")
                meta[k.strip()] = v.strip()
            last = None
            continue
        bm = BULLET_RE.match(line)
        if bm:
            last = bm["name"]
            bullets[last] = bm["text"].strip()
            continue
        if last and line.startswith("  ") and line.strip():
            bullets[last] += " " + line.strip()
    while block and not block[-1].strip():
        block = block[:-1]
    rule = Rule(id=m["id"], guide=guide, anchor=m["anchor"], title=m["title"],
                topic="", topic_file=path.name, order=0, meta=meta,
                bullets=bullets, block="\n".join(block))
    for raw in split_lint_field(meta.get("lint", "")):
        try:
            rule.lint.append(parse_lint_key(raw))
        except re.error as e:
            problem(f"bad lint regex {raw!r}: {e}")
    return rule


# --------------------------------------------------------------------------
# Helpers: subprocesses, git, go


def run_cmd(cmd, cwd=None, env=None, timeout=None, stdin=None):
    """Runs cmd and returns the CompletedProcess, or None when the executable
    does not exist. A timeout raises subprocess.TimeoutExpired."""
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout, input=stdin,
                              capture_output=True, text=True)
    except FileNotFoundError:
        return None


def module_root(start: Path) -> tuple[Path, str]:
    res = run_cmd(["go", "env", "GOMOD"], cwd=start)
    if res is None:
        die("the go command is not on PATH")
    gomod = res.stdout.strip()
    if not gomod or gomod == os.devnull:
        die(f"{start} is not inside a Go module (no go.mod found)")
    root = Path(gomod).parent
    path = ""
    for line in Path(gomod).read_text(encoding="utf-8").splitlines():
        if line.startswith("module "):
            path = line.split()[1].strip('"')
            break
    return root, path


def go_list(cwd: Path, patterns: list[str]) -> list[dict]:
    fields = "Dir,ImportPath,Name,GoFiles,CgoFiles,TestGoFiles,XTestGoFiles,Error"
    res = run_cmd(["go", "list", "-e", f"-json={fields}", *patterns], cwd=cwd)
    if res is None or res.returncode != 0:
        die(f"go list failed: {res.stderr.strip() if res else 'go not found'}")
    pkgs, dec, s, i = [], json.JSONDecoder(), res.stdout, 0
    while i < len(s):
        while i < len(s) and s[i].isspace():
            i += 1
        if i >= len(s):
            break
        obj, i = dec.raw_decode(s, i)
        pkgs.append(obj)
    return pkgs


GENERATED_RE = re.compile(r"^// Code generated .* DO NOT EDIT\.$")


def rel_to(p: Path, root: Path) -> str:
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        die(f"{p} is outside the module at {root}")
        raise  # unreachable


def is_generated(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                if GENERATED_RE.match(line.rstrip("\n")):
                    return True
                if line.startswith("package "):
                    return False
    except OSError:
        return False
    return False


def count_lines(path: Path) -> int:
    try:
        with path.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def git(root: Path, *args) -> str | None:
    res = run_cmd(["git", *args], cwd=root)
    if res is None or res.returncode != 0:
        return None
    return res.stdout


def resolve_base(root: Path, base: str | None) -> str:
    if base:
        if git(root, "rev-parse", "--verify", "--quiet", base + "^{commit}") is None:
            die(f"unknown git revision {base!r}")
        mb = git(root, "merge-base", "HEAD", base)
        return mb.strip() if mb else base
    for cand in ("origin/HEAD", "origin/main", "origin/master", "main", "master"):
        if git(root, "rev-parse", "--verify", "--quiet", cand + "^{commit}") is None:
            continue
        mb = git(root, "merge-base", "HEAD", cand)
        if mb and mb.strip() != git(root, "rev-parse", "HEAD").strip():
            return mb.strip()
    return "HEAD"  # on the default branch itself: review uncommitted changes


HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_lines(root: Path, base: str) -> dict[str, list[tuple[int, int]]]:
    """Maps module-relative .go paths to changed line ranges (new side)."""
    top = git(root, "rev-parse", "--show-toplevel")
    if top is None:
        die("--diff needs a git repository")
    top = Path(top.strip())
    out = git(root, "diff", "--unified=0", "--no-color", "--no-ext-diff", base, "--", "*.go")
    changes: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
    cur = None
    for line in (out or "").splitlines():
        if line.startswith("+++ "):
            p = line[4:].strip()
            cur = None if p == "/dev/null" else p[2:] if p.startswith("b/") else p
            continue
        m = HUNK_RE.match(line)
        if m and cur:
            start, n = int(m.group(1)), int(m.group(2) or "1")
            if n > 0:
                changes[cur].append((start, start + n - 1))
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "--full-name",
                    "--", "*.go")
    for p in (untracked or "").splitlines():
        if p.strip():
            changes[p.strip()] = [(1, 10**9)]
    result = {}
    for p, ranges in changes.items():
        abs_p = top / p
        try:
            rel = abs_p.resolve().relative_to(root.resolve())
        except ValueError:
            continue  # outside this module
        result[rel.as_posix()] = ranges
    return result


# --------------------------------------------------------------------------
# prepare


@dataclasses.dataclass
class SourceFile:
    path: str      # module-relative, slash-separated
    pkg: str       # module-relative directory
    test: bool
    lines: int


def collect_scope(root: Path, targets: list[str], include_tests: bool):
    """Resolves targets (go list patterns, directories, .go files; relative to
    the current directory) to the Go files to review."""
    cwd = Path.cwd()
    patterns, only_files = [], set()
    for t in targets or ["./..."]:
        p = (cwd / t).resolve()
        if "..." not in t and p.is_file() and p.suffix == ".go":
            only_files.add(rel_to(p, root))
            patterns.append(str(p.parent))
        elif "..." not in t and p.is_dir():
            patterns.append(str(p) + "/...")
        else:
            patterns.append(t)  # a go list pattern: ./..., ./pkg/..., import path
    pkgs = go_list(cwd, sorted(set(patterns)))
    files, skipped_generated, pkg_errors = [], 0, []
    for pkg in pkgs:
        d = Path(pkg.get("Dir", ""))
        try:
            rel_dir = d.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        if pkg.get("Error"):
            pkg_errors.append(f"{pkg.get('ImportPath')}: {pkg['Error'].get('Err', '')}")
        groups = [(pkg.get("GoFiles", []) + pkg.get("CgoFiles", []), False)]
        if include_tests:
            groups.append((pkg.get("TestGoFiles", []) + pkg.get("XTestGoFiles", []), True))
        for names, is_test in groups:
            for name in names:
                rel = name if rel_dir == "." else f"{rel_dir}/{name}"
                if only_files and rel not in only_files:
                    continue
                full = root / rel
                if is_generated(full):
                    skipped_generated += 1
                    continue
                files.append(SourceFile(rel, rel_dir, is_test, count_lines(full)))
    files.sort(key=lambda f: f.path)
    return files, sorted(set(patterns)), skipped_generated, pkg_errors


def issue_check(linter: str, text: str) -> tuple[str | None, str]:
    if linter in PREFIXED_LINTERS:
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*): (.*)$", text, re.S)
        if m:
            return m.group(1), m.group(2)
    return None, text


def map_issue(rules: list[Rule], linter: str, check: str | None, text: str) -> list[Rule]:
    """Returns at most one rule per guide: the first matching one in catalog order."""
    hits, seen = [], set()
    for r in rules:
        if r.guide in seen:
            continue
        if any(k.matches(linter, check, text) for k in r.lint):
            hits.append(r)
            seen.add(r.guide)
    return hits


def run_golangci(root: Path, patterns: list[str], include_tests: bool, out: Path):
    exe = shutil.which("golangci-lint")
    if exe is None:
        return {"status": "missing"}, []
    ver = run_cmd([exe, "--version"])
    m = re.search(r"version (\S+)", ver.stdout if ver else "")
    version = f"golangci-lint {m.group(1)}" if m else "golangci-lint (unknown version)"
    cmd = [exe, "run", "--config", str(CONFIG), "--output.json.path", str(out),
           "--output.text.path", os.devnull, "--show-stats=false",
           "--issues-exit-code=0", "--allow-parallel-runners",
           f"--tests={'true' if include_tests else 'false'}", *patterns]
    status = {"status": "ok", "version": version, "command": " ".join(cmd)}
    try:
        res = run_cmd(cmd, cwd=root, timeout=1800)
    except subprocess.TimeoutExpired:
        return dict(status, status="timeout"), []
    if res.returncode != 0:
        status["status"] = "error"
        status["stderr"] = res.stderr[-2000:]
    try:
        data = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        status["status"] = "error"
        return status, []
    if (data.get("Report") or {}).get("Error"):
        status["report_error"] = data["Report"]["Error"]
    return status, data.get("Issues") or []


def conflict_losers(rules: list, guides: list[str]) -> dict[str, list[str]]:
    """Returns {rule id: [what it contradicts]} for the rules that lose a
    conflict in a run over the given guides.

    A conflict recorded on either side counts, and the rule of the
    lower-priority guide loses. A reference to a section that has no rule of its
    own (such as google-decisions:non-decisions) still counts when that guide is
    part of the run. Works on Rule objects and on rules.json dicts."""
    def get(r, key):
        return r[key] if isinstance(r, dict) else getattr(r, key)

    def refs(r):
        return r["conflicts"] if isinstance(r, dict) else r.meta_list("conflicts")

    def prio(guide):
        return GUIDES[guide].priority if guide in GUIDES else 99

    by_ref: dict[str, list] = collections.defaultdict(list)
    for r in rules:
        by_ref[f"{get(r, 'guide')}:{get(r, 'anchor')}"].append(r)  # base id: all rules
        if "/" in get(r, "id"):
            by_ref[get(r, "id")].append(r)  # qualified id: that rule only
    losers: dict[str, list[str]] = collections.defaultdict(list)

    def lose(loser_id, winner):
        if winner not in losers[loser_id]:
            losers[loser_id].append(winner)

    for r in rules:
        rid, rg = get(r, "id"), get(r, "guide")
        if rg not in guides:
            continue
        for ref in refs(r):
            ref_guide = ref.split(":", 1)[0]
            if ref_guide not in guides or prio(ref_guide) == prio(rg):
                continue
            if prio(ref_guide) < prio(rg):
                lose(rid, ref)  # this rule contradicts a higher-priority section
            else:
                for other in by_ref.get(ref, []):
                    lose(get(other, "id"), rid)  # a higher rule contradicts it
    return dict(losers)


def build_bundles(rules: list[Rule], guides: list[str], run_dir: Path):
    """Writes the reviewer rule bundles and returns {group: [paths]} plus the
    rules left out because they contradict a higher-priority guide.

    Rules that merely overlap a higher-priority rule stay in: the lower-priority
    guide is often the more specific one (decisions elaborates the guide), and
    the report folds duplicate findings into one."""
    dropped = {}
    losers = conflict_losers(rules, guides) if len(guides) > 1 else {}
    groups: dict[str, list[Rule]] = {"decl": [], "code": [], "test": []}
    for r in rules:
        if r.check not in ("llm", "lint+llm"):
            continue
        if r.id in losers:
            dropped[r.id] = f"contradicts {', '.join(losers[r.id])}"
            continue
        group = {"decl": "decl", "repo": "decl", "body": "code", "test": "test"}.get(r.scope)
        if group:
            groups[group].append(r)

    paths: dict[str, list[str]] = {}
    for group, members in groups.items():
        if not members:
            continue
        parts, cur, size = [], [], 0
        for r in members:
            if cur and size + len(r.block) > BUNDLE_SPLIT_CHARS and \
                    (r.topic, r.guide) != (cur[-1].topic, cur[-1].guide):
                parts.append(cur)
                cur, size = [], 0
            cur.append(r)
            size += len(r.block)
        parts.append(cur)
        paths[group] = []
        for i, part in enumerate(parts, 1):
            name = f"bundle-{group}" + (f"-{i}" if len(parts) > 1 else "") + ".md"
            text = render_bundle(group, part, multi=len(guides) > 1)
            (run_dir / name).write_text(text, encoding="utf-8")
            paths[group].append(str(run_dir / name))
    return paths, dropped


BUNDLE_INTRO = {
    "decl": "declarations, doc comments, package layout and API shape",
    "code": "code inside function bodies (non-test files)",
    "test": "test code (_test.go files)",
}


def render_bundle(group: str, rules: list[Rule], multi: bool) -> str:
    out = [f"# Rule bundle: {BUNDLE_INTRO[group]}", "",
           f"{len(rules)} rules. Report findings only against these rule ids. "
           "`check=lint+llm` means linters already report part of the rule: "
           "report only what the `look for` bullet leaves to you.", ""]
    if multi:
        out += ["Rules from several guides are combined here and some cover the same "
                "concern (see `overlaps`). Report each problem once, under the most "
                "specific rule that fits; the report adds links to the related rules.", ""]
    cur = None
    for r in rules:
        key = (r.guide, r.topic)
        if key != cur:
            out += [f"## {GUIDES[r.guide].short} — {r.topic}", ""]
            cur = key
        out += [r.block, ""]
    return "\n".join(out)


def pack_bundles(paths: list[str], limit: int) -> list[list[str]]:
    """Packs bundle files into groups of at most limit characters (first fit,
    largest first); a bundle larger than limit gets a group of its own."""
    sizes = {p: Path(p).stat().st_size for p in paths}
    groups: list[list[str]] = []
    totals: list[int] = []
    for p in sorted(paths, key=lambda q: -sizes[q]):
        for i, total in enumerate(totals):
            if total + sizes[p] <= limit:
                groups[i].append(p)
                totals[i] += sizes[p]
                break
        else:
            groups.append([p])
            totals.append(sizes[p])
    return groups


def chunk_files(files: list[SourceFile], limit: int) -> list[list[SourceFile]]:
    """Packs files into chunks of about limit lines, keeping a package's files
    together while they fit."""
    chunks, cur, size = [], [], 0
    for f in files:
        if cur and size + f.lines > limit and (f.pkg != cur[-1].pkg or size >= limit):
            chunks.append(cur)
            cur, size = [], 0
        cur.append(f)
        size += f.lines
    if cur:
        chunks.append(cur)
    return chunks


def split_outline(text: str, limit: int) -> list[str]:
    parts, cur = [], ""
    for block in re.split(r"(?m)^(?=== )", text):
        if cur and len(cur) + len(block) > limit:
            parts.append(cur)
            cur = ""
        cur += block
    if cur.strip():
        parts.append(cur)
    return parts


def build_outline(root: Path, files: list[SourceFile], out: Path) -> str | None:
    """Writes the declaration outline of the non-test files; returns an error
    note instead of failing the run when go run does not work."""
    paths = "\n".join(f.path for f in files if not f.test)
    if not paths:
        return None
    env = dict(os.environ, GOFLAGS="", GOWORK="off")
    try:
        res = run_cmd(["go", "run", OUTLINE_GO.name, "-root", str(root)],
                      cwd=OUTLINE_GO.parent, env=env, stdin=paths, timeout=600)
    except subprocess.TimeoutExpired:
        return "outline timed out"
    if res is None or res.returncode != 0:
        return f"outline failed: {(res.stderr if res else 'go not found').strip()[:500]}"
    out.write_text(res.stdout, encoding="utf-8")
    return None


def task_text(task: dict, run: dict) -> str:
    template = REVIEWER.read_text(encoding="utf-8")
    lines = []
    if task.get("outline"):
        lines.append(f"- Declaration outline to review: `{task['outline']}` "
                     "(open the source files it names to confirm a finding)")
        if run["mode"] == "diff":
            lines.append("- Changed lines per file (review only declarations that "
                         "overlap them):")
            for path, hunks in sorted(run["changes"].items()):
                if path in task.get("outline_files", []):
                    spans = ", ".join(f"{a}-{b}" if b != a else f"{a}"
                                      for a, b in hunks if b < 10**9) or "new file"
                    lines.append(f"  - `{path}`: {spans}")
    if task.get("files"):
        lines.append("- Source files to review (read each one completely; paths are "
                     f"relative to the module root `{run['root']}`):")
        for f in task["files"]:
            hunks = run["changes"].get(f["path"]) if run["mode"] == "diff" else None
            extra = ""
            if hunks:
                spans = ", ".join(f"{a}-{b}" if b != a else f"{a}" for a, b in hunks
                                  if b < 10**9) or "new file"
                extra = f" — changed lines: {spans}"
            kind = "test" if f["test"] else "code"
            lines.append(f"  - `{f['path']}` ({f['lines']} lines, {kind}){extra}")
    bundles = "\n".join(f"- `{b}`" for b in task["bundles"])
    mode_note = ("Diff review: report only problems on the changed lines listed above "
                 "(or problems the change itself introduces elsewhere)."
                 if run["mode"] == "diff" else "Full review of the listed scope.")
    values = {
        "TASK_ID": task["id"],
        "GUIDES": ", ".join(GUIDES[g].name for g in run["guides"]),
        "BUNDLES": bundles,
        "INPUT": "\n".join(lines),
        "OUTPUT": task["output"],
        "MODE": mode_note,
        "ROOT": run["root"],
    }
    for k, v in values.items():
        template = template.replace("{{" + k + "}}", v)
    return template


def cmd_prepare(args) -> None:
    guides = parse_guides(args.guides)
    root, modpath = module_root(Path.cwd())
    files, patterns, n_generated, pkg_errors = collect_scope(root, args.targets,
                                                             not args.no_tests)
    mode, base, changes = "full", None, {}
    if args.diff is not None:
        mode = "diff"
        base = resolve_base(root, args.diff or None)
        changes = changed_lines(root, base)
        files = [f for f in files if f.path in changes]
    if not files:
        die("no Go files in scope" + (" (no changed .go files)" if mode == "diff" else ""))

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    label = guides[0] if len(guides) == 1 else "all" if len(guides) == len(GUIDES) \
        else "+".join(guides)
    base_dir = Path(args.out).resolve() if args.out else root / ".go-style"
    base_dir.mkdir(parents=True, exist_ok=True)
    gi = base_dir / ".gitignore"
    if not args.out and not gi.exists():
        gi.write_text("# Created by the go-style skills: ignore everything here.\n*\n")
    run_dir = base_dir / "runs" / f"{stamp}-{label}"
    n = 1
    while run_dir.exists():  # two runs in the same second
        n += 1
        run_dir = base_dir / "runs" / f"{stamp}-{label}-{n}"
    (run_dir / "findings").mkdir(parents=True)
    (run_dir / "tasks").mkdir()

    rules = load_rules(guides)
    if not rules:
        die("no rules found for " + ", ".join(guides))
    (run_dir / "rules.json").write_text(
        json.dumps([r.summary() for r in rules], indent=1), encoding="utf-8")

    # Linters.
    lint_status, issues = {"status": "skipped"}, []
    if not args.no_lint:
        whole_module = mode == "full" and not args.targets and Path.cwd() == root
        lint_patterns = ["./..."] if whole_module else \
            sorted({"./" + f.pkg if f.pkg != "." else "." for f in files})
        lint_status, issues = run_golangci(root, lint_patterns, not args.no_tests,
                                           run_dir / "golangci.json")
    scope_paths = {f.path for f in files}
    mapped, unmapped, build_errors = [], collections.Counter(), []
    # Issues no selected guide covers but another guide does: reported as a
    # count, so a single-guide run does not hide them silently.
    other_rules = load_rules([g for g in GUIDES if g not in guides])
    elsewhere: collections.Counter = collections.Counter()
    other_issues: list[dict] = []
    for it in issues:
        pos = it.get("Pos") or {}
        path = (pos.get("Filename") or "").replace("\\", "/")
        if path.startswith(str(root)):
            path = Path(path).relative_to(root).as_posix()
        linter, text = it.get("FromLinter", ""), it.get("Text", "")
        if linter == "typecheck":
            build_errors.append(f"{path}:{pos.get('Line')}: {text.strip()[:300]}")
            continue
        if path not in scope_paths:
            continue
        line = int(pos.get("Line") or 0)
        if mode == "diff" and not args.whole_files and \
                not in_ranges(line, changes.get(path, []), slack=0):
            continue
        check, body = issue_check(linter, text)
        hits = map_issue(rules, linter, check, body)
        if not hits:
            other = map_issue(other_rules, linter, check, body)
            if other:
                for r in other:
                    elsewhere[r.guide] += 1
                top = other[0]  # highest-priority guide first
                other_issues.append({"tool": linter, "file": path, "line": line,
                                     "message": text.strip(), "rule": top.id,
                                     "title": top.title, "url": top.url,
                                     "guide": top.guide})
            else:
                unmapped[f"{linter}:{check}" if check else linter] += 1
            continue
        for r in hits:
            mapped.append({"source": "lint", "tool": linter, "check": check,
                           "rule": r.id, "file": path, "line": line,
                           "col": int(pos.get("Column") or 0), "message": text.strip(),
                           "snippet": ((it.get("SourceLines") or [""])[0]).strip()})
    with (run_dir / "lint.jsonl").open("w", encoding="utf-8") as f:
        for m in mapped:
            f.write(json.dumps(m) + "\n")
    (run_dir / "lint-other.json").write_text(json.dumps(other_issues, indent=1),
                                            encoding="utf-8")

    # Reviewer inputs.
    bundles, dropped = build_bundles(rules, guides, run_dir)
    outline_note = None
    total_lines = sum(f.lines for f in files)
    code_files = [f for f in files if not f.test]
    test_files = [f for f in files if f.test]
    tasks = []

    def add_task(kind, bundle_paths, files_=None, outline=None):
        tid = f"{kind}{len([t for t in tasks if t['kind'] == kind]) + 1:02d}"
        tasks.append({
            "id": tid, "kind": kind, "bundles": bundle_paths,
            "files": [dataclasses.asdict(f) for f in (files_ or [])],
            "outline": outline, "output": str(run_dir / "findings" / f"{tid}.jsonl"),
            "lines": sum(f.lines for f in (files_ or [])),
        })

    if not args.no_llm:
        small = [p for g in ("decl", "code") for p in bundles.get(g, [])]
        if test_files:
            small += bundles.get("test", [])
        if total_lines <= args.single_task_lines and small:
            # Small scope: one task per bundle, each reading all files. The tasks
            # run in parallel, so the wait is that of the slowest bundle rather
            # than of all rules read in series.
            for b in small:
                add_task("all", [b], files)
        else:
            if bundles.get("decl"):
                outline_path = run_dir / "outline.txt"
                outline_note = build_outline(root, files, outline_path)
                if outline_note is None and outline_path.exists():
                    parts = split_outline(outline_path.read_text(encoding="utf-8"),
                                          OUTLINE_PART_CHARS)
                    for i, part in enumerate(parts, 1):
                        p = run_dir / f"outline-{i}.txt" if len(parts) > 1 else outline_path
                        p.write_text(part, encoding="utf-8")
                        names = re.findall(r"(?m)^-- (\S+) · ", part)
                        for b in bundles["decl"]:
                            add_task("decl", [b], outline=str(p))
                            tasks[-1]["outline_files"] = names
            for chunk in chunk_files(code_files, args.chunk_lines):
                for b in bundles.get("code", []):
                    add_task("code", [b], chunk)
            for chunk in chunk_files(test_files, args.chunk_lines):
                for b in bundles.get("test", []):
                    add_task("test", [b], chunk)

    run = {
        "run_id": run_dir.name, "run_dir": str(run_dir), "created": stamp,
        "root": str(root), "module": modpath, "guides": guides, "mode": mode,
        "base": base, "targets": args.targets or ["./..."], "patterns": patterns,
        "include_tests": not args.no_tests, "whole_files": args.whole_files,
        "changes": changes, "lint": lint_status, "build_errors": build_errors,
        "package_errors": pkg_errors, "generated_skipped": n_generated,
        "files": len(files), "lines": total_lines,
        "lint_mapped": len(mapped),
        "lint_issues": len({(m["tool"], m["file"], m["line"], m["message"]) for m in mapped}),
        "conflict_losers": conflict_losers(rules, guides) if len(guides) > 1 else {},
        "lint_unmapped": dict(unmapped),
        "lint_other_guides": dict(elsewhere), "lint_other_total": len(other_issues),
        "bundles": bundles, "dropped_rules": dropped, "outline_error": outline_note,
        "tasks": tasks, "commit": head_commit(root),
    }
    for t in tasks:
        path = run_dir / "tasks" / f"{t['id']}.md"
        path.write_text(task_text(t, run), encoding="utf-8")
        t["task_file"] = str(path)
    (run_dir / "run.json").write_text(json.dumps(run, indent=1), encoding="utf-8")
    print_prepare_summary(run, mapped, rules)


def other_guides_text(counts: dict, total: int | None = None) -> str:
    """"N issues (Guide a, Guide b …)": an issue can map to rules of several guides,
    so the per-guide numbers may add up to more than N."""
    parts = [f"{GUIDES[g].short} {n}" for g, n in
             sorted(counts.items(), key=lambda kv: GUIDES[kv[0]].priority)]
    n = total if total is not None else sum(counts.values())
    return f"{n} (rules in {', '.join(parts)}); run /go-style to include them"


def in_ranges(line: int, ranges, slack: int) -> bool:
    return any(a - slack <= line <= b + slack for a, b in ranges)


def head_commit(root: Path) -> str:
    sha = git(root, "rev-parse", "--short", "HEAD")
    if sha is None:
        return ""
    dirty = git(root, "status", "--porcelain", "--untracked-files=no")
    return sha.strip() + (" (+uncommitted changes)" if dirty and dirty.strip() else "")


def parse_guides(value: str) -> list[str]:
    if value == "all":
        return list(GUIDES)
    guides = [g.strip() for g in value.split(",") if g.strip()]
    for g in guides:
        if g not in GUIDES:
            die(f"unknown guide {g!r}; known: {', '.join(GUIDES)}, all")
    return sorted(set(guides), key=lambda g: GUIDES[g].priority)


def print_prepare_summary(run: dict, mapped: list, rules: list[Rule]) -> None:
    print(f"run: {run['run_dir']}")
    print(f"module: {run['module']} ({run['root']}) · guides: {', '.join(run['guides'])}")
    scope = f"mode: {run['mode']}"
    if run["mode"] == "diff":
        scope += f" against {run['base'][:12]}"
    print(f"{scope} · {run['files']} files, {run['lines']} lines "
          f"(generated skipped: {run['generated_skipped']})")
    lint = run["lint"]
    if lint["status"] == "ok":
        losers = run.get("conflict_losers", {})
        top = collections.Counter(m["rule"] for m in mapped
                                  if m["rule"] not in losers).most_common(5)
        print(f"golangci-lint: {run.get('lint_issues', len(mapped))} issues mapped to rules"
              + (f"; top: {', '.join(f'{r} ×{n}' for r, n in top)}" if top else ""))
    else:
        print(f"golangci-lint: {lint['status'].upper()}"
              + (f" — {lint.get('stderr', '').strip()[:300]}" if lint.get("stderr") else ""))
    if run.get("lint_other_guides"):
        print("more linter issues under other guides (not in this report): " +
              other_guides_text(run["lint_other_guides"], run.get("lint_other_total")))
    if run["build_errors"]:
        print(f"WARNING: {len(run['build_errors'])} type-check errors — the code does not "
              "build, type-aware checks are incomplete (see run.json build_errors)")
    if run["outline_error"]:
        print(f"WARNING: {run['outline_error']}")
    reviewed = sum(1 for r in rules if r.check != "lint")
    print(f"rules: {len(rules)} ({reviewed} need review); "
          f"left out (contradict a higher-priority guide): {len(run['dropped_rules'])}")
    if not run["tasks"]:
        print("tasks: none (lint-only run)")
        return
    print(f"tasks: {len(run['tasks'])} reviewer subagents")
    for t in run["tasks"]:
        what = f"outline {Path(t['outline']).name}" if t["outline"] else \
            f"{len(t['files'])} files, {t['lines']} lines"
        print(f"  {t['id']}: {what} · {', '.join(Path(b).name for b in t['bundles'])} "
              f"-> {t['task_file']}")


# --------------------------------------------------------------------------
# report


SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}


@dataclasses.dataclass
class Finding:
    source: str        # lint | review
    tool: str          # linter name or "review"
    rule: str
    file: str
    line: int
    message: str
    snippet: str = ""
    fix: str = ""
    confidence: str = ""
    severity: str = ""
    also_lines: list = dataclasses.field(default_factory=list)
    see_also: list = dataclasses.field(default_factory=list)
    verified: bool = True
    why_unverified: str = ""
    task: str = ""


def norm_ws(s: str) -> str:
    return " ".join(s.split())


def verify_location(root: Path, f: Finding, cache: dict) -> bool:
    """Checks that the file exists and that the snippet is on (or near) the
    reported line; moves the line to the snippet when it is found elsewhere."""
    path = root / f.file
    if f.file not in cache:
        try:
            cache[f.file] = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            cache[f.file] = None
    lines = cache[f.file]
    if lines is None:
        return False
    if not f.snippet:
        return 1 <= f.line <= len(lines)
    snip = norm_ws(f.snippet)
    if not snip:
        return 1 <= f.line <= len(lines)
    lo, hi = max(1, f.line - 3), min(len(lines), f.line + 3)
    for n in [f.line] + [i for i in range(lo, hi + 1) if i != f.line]:
        if 1 <= n <= len(lines) and snip in norm_ws(lines[n - 1]):
            f.line = n
            return True
    found = [i + 1 for i, text in enumerate(lines) if snip in norm_ws(text)]
    if len(found) == 1:
        f.line = found[0]
        return True
    return False


def load_review_findings(run: dict, known: dict, rejected: list) -> list[Finding]:
    out = []
    for path in sorted(Path(run["run_dir"], "findings").glob("*.jsonl")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except ValueError:
                rejected.append(f"{path.name}:{n}: not JSON")
                continue
            rule = str(d.get("rule", "")).strip()
            if rule not in known:
                # Accept a bare anchor when it names exactly one known rule.
                cands = [k for k in known if k.split(":", 1)[-1] == rule]
                if len(cands) != 1:
                    rejected.append(f"{path.name}:{n}: unknown rule {rule!r}")
                    continue
                rule = cands[0]
            file = str(d.get("file", "")).replace("\\", "/")
            if file.startswith(run["root"]):
                file = file[len(run["root"]):].lstrip("/")
            file = file[2:] if file.startswith("./") else file
            try:
                line_no = int(d.get("line") or 0)
            except (TypeError, ValueError):
                line_no = 0
            sev = str(d.get("severity") or "")
            if sev and not d.get("bug") and sev in SEV_RANK:
                sev = "lower:" + sev  # without bug=true a severity may only lower
            out.append(Finding(
                source="review", tool="review", rule=rule, file=file, line=line_no,
                message=str(d.get("message", "")).strip(),
                snippet=str(d.get("snippet", "")), fix=str(d.get("fix", "")).strip(),
                confidence=str(d.get("confidence", "")), severity=sev,
                also_lines=[int(x) for x in d.get("also_lines") or []
                            if str(x).isdigit()],
                task=path.stem))
    return out


def cmd_report(args) -> None:
    run_dir = Path(args.run).resolve() if args.run else latest_run()
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    root = Path(run["root"])
    rules = {r["id"]: r for r in json.loads((run_dir / "rules.json").read_text())}
    guides = run["guides"]
    multi = len(guides) > 1
    rejected: list[str] = []

    findings = []
    lint_path = run_dir / "lint.jsonl"
    if lint_path.exists():
        for line in lint_path.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            findings.append(Finding(source="lint", tool=d["tool"], rule=d["rule"],
                                    file=d["file"], line=d["line"],
                                    message=d["message"], snippet=""))
    findings += load_review_findings(run, rules, rejected)

    cache: dict = {}
    for f in findings:
        rule = rules[f.rule]
        sev = rule["severity"]
        if f.severity.startswith("lower:"):
            asked = f.severity.split(":", 1)[1]
            if SEV_RANK[asked] > SEV_RANK.get(sev, 0):
                sev = asked  # a minor instance of the rule
        elif f.severity in SEV_RANK:
            sev = f.severity  # a correctness bug the reviewer marked bug=true
            f.message = "Bug: " + f.message if not f.message.startswith("Bug") else f.message
        f.severity = sev
        if f.source != "review":
            continue
        if not verify_location(root, f, cache):
            f.verified, f.why_unverified = False, "quoted code not found at the line"
        elif run["mode"] == "diff" and not run["whole_files"] and \
                not in_ranges(f.line, run["changes"].get(f.file, []), slack=3):
            f.verified, f.why_unverified = False, "outside the changed lines"

    findings = fold_lint_duplicates(findings, rules)

    findings = merge_review_into_lint(findings)

    skipped: list = []
    if multi:
        findings, skipped = apply_priority(findings, rules)

    findings.sort(key=lambda f: (rules[f.rule]["order"], f.file, f.line))
    verified = [f for f in findings if f.verified]
    unverified = [f for f in findings if not f.verified]

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    label = run["run_id"].split("-", 2)[-1]
    out = Path(args.output).resolve() if args.output else \
        Path(run_dir).parent.parent / "reports" / f"{stamp}-{label}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = render_report(run, rules, verified, unverified, skipped, rejected)
    out.write_text(text, encoding="utf-8")
    js = out.with_suffix(".json")
    js.write_text(json.dumps({
        "run": run["run_id"], "guides": guides, "mode": run["mode"],
        "health": run_health(run),
        "dropped_rules": sorted(run["dropped_rules"]),
        "findings": [dict(dataclasses.asdict(f), url=rules[f.rule]["url"],
                          title=rules[f.rule]["title"]) for f in findings],
        "skipped": [dict(dataclasses.asdict(f), contradicts=w) for f, w in skipped],
        "other_guides": load_other_issues(run_dir) if not multi else [],
    }, indent=1), encoding="utf-8")
    print_report_summary(run, rules, verified, unverified, skipped, rejected, out)


def load_other_issues(run_dir: Path) -> list[dict]:
    path = Path(run_dir) / "lint-other.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def run_health(run: dict) -> dict:
    """What limits the result of a run, in one place for the answer."""
    tasks = run.get("tasks", [])
    return {
        "lint": run["lint"]["status"],
        "lint_version": run["lint"].get("version", ""),
        "build_errors": len(run.get("build_errors", [])),
        "package_errors": len(run.get("package_errors", [])),
        "tasks": len(tasks),
        "tasks_without_output": [t["id"] for t in tasks if not Path(t["output"]).exists()],
        "outline_error": run.get("outline_error"),
        "issues_under_other_guides": run.get("lint_other_total",
                                             sum((run.get("lint_other_guides") or {}).values())),
        "git": bool(run.get("commit")),
    }


def merge_review_into_lint(findings: list[Finding]) -> list[Finding]:
    """A reviewer finding of the same rule within two lines of a linter finding is
    the same problem: keep one entry at the linter's line, carrying the
    reviewer's explanation and fix, which are usually the more actionable part.
    Exact duplicates among reviewer findings are dropped."""
    lint = [f for f in findings if f.source == "lint"]
    review = [f for f in findings if f.source != "lint"]
    by_rule_file: dict[tuple, list[Finding]] = collections.defaultdict(list)
    for f in lint:
        by_rule_file[(f.rule, f.file)].append(f)
    kept, seen = [], set()
    for f in review:
        twin = next((k for k in by_rule_file.get((f.rule, f.file), [])
                     if abs(k.line - f.line) <= 2), None)
        if twin is not None and f.verified:
            twin.message = f"{f.message} (linter: {twin.message})"
            twin.fix = twin.fix or f.fix
            twin.confidence = f.confidence
            continue
        key = (f.rule, f.file, f.line)
        if key in seen:
            continue
        seen.add(key)
        kept.append(f)
    return lint + kept


def fold_lint_duplicates(findings: list[Finding], rules: dict) -> list[Finding]:
    """Folds linter findings that describe one problem into one entry: two
    linters reporting the same rule in one file within a few lines (staticcheck
    SA2002 at the `go` statement and vet testinggoroutine at the t.Fatal call).
    staticcheck ST1016 names no line of its own (it reports a type's receivers
    at some method), so it is dropped when revive flagged that file already."""
    lint = [f for f in findings if f.source == "lint"]
    rest = [f for f in findings if f.source != "lint"]
    lint.sort(key=lambda f: (f.file, f.line))
    kept: list[Finding] = []
    for f in lint:
        if f.tool == "staticcheck" and f.message.startswith("ST1016"):
            if any(k.rule == f.rule and k.file == f.file and k.tool == "revive"
                   for k in lint):
                continue
        twin = next((k for k in kept if k.rule == f.rule and k.file == f.file
                     and k.tool != f.tool and abs(k.line - f.line) <= 5), None)
        if twin is not None:
            if f.line != twin.line and f.line not in twin.also_lines:
                twin.also_lines.append(f.line)
            continue
        kept.append(f)
    return kept + rest


def apply_priority(findings: list[Finding], rules: dict):
    """Multi-guide runs: one entry per problem, under the highest-priority guide.

    - A finding of a rule that contradicts a higher-priority rule is dropped
      (a conflict recorded on either side counts).
    - One linter issue maps to a rule in each guide: it is reported once, under
      the highest-priority rule, with the others as "see also" links.
    - A reviewer finding whose rule overlaps a higher-priority rule that has a
      finding on the same line is folded into it the same way.
    """
    def prio(rule_id):
        return GUIDES[rules[rule_id]["guide"]].priority

    def base(rule_id):
        r = rules[rule_id]
        return f"{r['guide']}:{r['anchor']}"

    losers = conflict_losers(list(rules.values()),
                             sorted({r["guide"] for r in rules.values()}))
    skipped: list[tuple[Finding, str]] = []
    kept = []
    for f in findings:
        if f.rule in losers:
            skipped.append((f, losers[f.rule][0]))
            continue
        kept.append(f)

    # One linter issue, several guides.
    issues: dict[tuple, list[Finding]] = collections.defaultdict(list)
    for f in kept:
        if f.source == "lint":
            issues[(f.tool, f.message, f.file, f.line)].append(f)
    folded = set()
    for group in issues.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda f: (prio(f.rule), rules[f.rule]["order"]))
        for other in group[1:]:
            group[0].see_also.append(other.rule)
            folded.add(id(other))
    kept = [f for f in kept if id(f) not in folded]

    # Overlapping rules with findings on the same line.
    at: dict[tuple, list[Finding]] = collections.defaultdict(list)
    for f in kept:
        at[(f.file, f.line)].append(f)
    result = []
    for f in kept:
        r = rules[f.rule]
        near = [g for d in range(-2, 3) for g in at.get((f.file, f.line + d), [])]
        higher = [g for g in near
                  if g is not f and prio(g.rule) < prio(f.rule) and
                  (base(g.rule) in r["overlaps"] or
                   base(f.rule) in rules[g.rule]["overlaps"])]
        if higher:
            higher[0].see_also.append(f.rule)
            continue
        result.append(f)
    return result, skipped


def prio_of(base_id: str) -> int:
    return GUIDES[base_id.split(":", 1)[0]].priority if ":" in base_id and \
        base_id.split(":", 1)[0] in GUIDES else 99


def latest_run() -> Path:
    root, _ = module_root(Path.cwd())
    runs = sorted((root / ".go-style" / "runs").glob("*"))
    if not runs:
        die("no runs found; run `prepare` first or pass --run")
    return runs[-1]


def md_link(rule: dict) -> str:
    return f"[{GUIDES[rule['guide']].short} › {rule['title']}]({rule['url']})"


def render_report(run, rules, findings, unverified, skipped, rejected) -> str:
    guides = run["guides"]
    title = GUIDES[guides[0]].name if len(guides) == 1 else \
        " + ".join(GUIDES[g].short for g in guides)
    sev_count = collections.Counter(f.severity for f in findings)
    src_count = collections.Counter(f.source for f in findings)
    target = ", ".join(run["targets"])
    mode = "full" if run["mode"] == "full" else f"diff against `{(run['base'] or '')[:12]}`"
    out = [f"# Go style review — {title}", "",
           f"- **Target:** `{target}` in `{run['module']}` (`{run['root']}`)",
           f"- **Mode:** {mode} · **Commit:** `{run['commit'] or 'n/a'}` · "
           f"**Run:** `{run['run_id']}`",
           f"- **Scope:** {run['files']} files, {run['lines']} lines"
           + (f" (generated files skipped: {run['generated_skipped']})"
              if run["generated_skipped"] else ""),
           f"- **Checks:** golangci-lint: {lint_line(run)} · review: "
           f"{len(run['tasks'])} subagent task(s)",
           f"- **Health:** {health_line(run)}", ""]

    out += ["## Summary", "", "| Severity | Findings |", "|---|---:|"]
    for s in SEVERITIES:
        out.append(f"| {s} | {sev_count.get(s, 0)} |")
    out += [f"| **total** | **{len(findings)}** (linters {src_count.get('lint', 0)}, "
            f"review {src_count.get('review', 0)}) |", ""]
    per_rule = collections.Counter(f.rule for f in findings)
    repeated = [(r, n) for r, n in per_rule.most_common(8) if n > 1]
    if repeated:
        top = ", ".join(f"{md_link(rules[r])} ×{n}" for r, n in repeated)
        out += [f"Most frequent: {top}", ""]
    must = [f for f in findings if f.severity == "must"]
    if must:
        out += ["### Must fix", ""]
        out += [f"- `{f.file}:{f.line}` — {f.message} ({md_link(rules[f.rule])})"
                + optional_mark(rules[f.rule]) for f in must[:30]]
        if len(must) > 30:
            out.append(f"- … and {len(must) - 30} more below")
        out.append("")

    out += ["## Findings by guide section", ""]
    if not findings:
        out += ["No findings.", ""]
    by_rule: dict[str, list[Finding]] = collections.OrderedDict()
    for f in findings:
        by_rule.setdefault(f.rule, []).append(f)
    cur_head = None
    for rid, items in by_rule.items():
        r = rules[rid]
        head = (r["guide"], r["topic"])
        if head != cur_head:
            out += [f"### {GUIDES[r['guide']].short} — {r['topic']}", ""]
            cur_head = head
        sevs = collections.Counter(f.severity for f in items)
        sev_text = next(iter(sevs)) if len(sevs) == 1 else \
            ", ".join(f"{s} {sevs[s]}" for s in SEVERITIES if sevs.get(s))
        out += [f"#### [{r['title']}]({r['url']}) · {sev_text} · {len(items)}", ""]
        if r["rule"]:
            out += [f"> {shorten(r['rule'], 320)}", ""]
        losing_to = [c for c in r["conflicts"]
                     if prio_of(c) < GUIDES[r["guide"]].priority]
        if losing_to:
            out += [f"> ⚠ Contradicts {', '.join(losing_to)}, which has priority — treat "
                    "these findings as optional.", ""]
        for i, f in enumerate(items):
            if i == 25:
                out += ["<details><summary>"
                        f"{len(items) - 25} more</summary>", ""]
            out.append(finding_line(f, rules))
        if len(items) > 25:
            out += ["", "</details>"]
        out.append("")

    if unverified:
        out += ["## Needs a manual check", "",
                "Reviewer findings whose location could not be confirmed (the quoted "
                "code was not found at the reported line, or it lies outside the "
                "changed lines). They may still be right.", ""]
        out += [finding_line(f, rules) for f in unverified]
        out.append("")

    notes = []
    if run["lint"]["status"] != "ok":
        notes.append(f"golangci-lint did not run cleanly ({run['lint']['status']}); "
                     "mechanical rules are missing from this report.")
    if run["build_errors"]:
        notes.append(f"{len(run['build_errors'])} type-check errors: the code does not "
                     "build, so type-aware linters saw only part of it. First: "
                     f"`{run['build_errors'][0][:200]}`")
    if run.get("outline_error"):
        notes.append(run["outline_error"])
    missing = [t["id"] for t in run["tasks"] if not Path(t["output"]).exists()]
    if missing:
        notes.append(f"Reviewer tasks without output: {', '.join(missing)} — their part "
                     "of the scope was not reviewed.")
    if run.get("lint_other_guides"):
        notes.append("Linter issues covered by other guides, not part of this report: " +
                     other_guides_text(run["lint_other_guides"],
                                       run.get("lint_other_total")) + ".")
    if skipped:
        notes.append(f"{len(skipped)} findings not reported because a higher-priority "
                     "guide disagrees (listed at the end).")
    if run["dropped_rules"]:
        notes.append(f"{len(run['dropped_rules'])} rules were not given to reviewers "
                     "because they contradict a higher-priority guide.")
    if rejected:
        notes.append(f"{len(rejected)} reviewer findings rejected (malformed or unknown "
                     "rule): " + "; ".join(rejected[:5]))
    if notes:
        out += ["## Notes", ""] + [f"- {n}" for n in notes] + [""]
    other = load_other_issues(run["run_dir"]) if len(guides) == 1 else []
    if other:
        out += ["## Also found by linters under other guides", "",
                "Not part of this guide, listed so that real bugs are not lost; "
                "`/go-style` reviews them in context.", ""]
        out += [f"- `{o['file']}:{o['line']}` — {o['message']} "
                f"([{GUIDES[o['guide']].short} › {o['title']}]({o['url']}))"
                for o in other[:40]]
        if len(other) > 40:
            out.append(f"- … and {len(other) - 40} more (see the .json report)")
        out.append("")
    if skipped:
        out += ["## Not reported: a higher-priority guide disagrees", ""]
        out += [f"- `{f.file}:{f.line}` — {f.message} ({md_link(rules[f.rule])}; "
                f"contradicts {w})" for f, w in skipped]
        out.append("")
    out += ["---", "",
            f"Produced by the go-style skills. Linter command: "
            f"`{run['lint'].get('command', 'n/a')}`", ""]
    return "\n".join(out)


def optional_mark(rule: dict) -> str:
    losing = [c for c in rule["conflicts"] if prio_of(c) < GUIDES[rule["guide"]].priority]
    return f" — ⚠ optional: contradicts {', '.join(losing)}" if losing else ""


def health_line(run: dict) -> str:
    h = run_health(run)
    parts = [f"linters {h['lint']}",
             "builds" if not h["build_errors"] else f"{h['build_errors']} type-check errors",
             f"review tasks {h['tasks'] - len(h['tasks_without_output'])}/{h['tasks']} done"]
    if h["issues_under_other_guides"]:
        parts.append(f"{h['issues_under_other_guides']} linter issues under other guides")
    if not h["git"]:
        parts.append("not a git checkout (no --diff)")
    return " · ".join(parts)


def lint_line(run) -> str:
    lint = run["lint"]
    if lint["status"] == "ok":
        n = run.get("lint_issues", run["lint_mapped"])
        return f"{n} issues mapped to rules ({lint.get('version', '')})"
    return lint["status"]


def finding_line(f: Finding, rules: dict) -> str:
    loc = f"`{f.file}:{f.line}`"
    if f.also_lines:
        loc += f" (also {', '.join(str(n) for n in f.also_lines[:8])})"
    src = f.tool if f.source == "lint" else "review"
    if f.confidence and f.source == "review":
        src += f", {f.confidence}"
    line = f"- {loc} — {f.message} _({src})_"
    if not f.verified and f.why_unverified:
        line += f" — **{f.why_unverified}**"
    if f.fix:
        line += f"\n  - fix: `{shorten(f.fix, 200)}`"
    if f.see_also:
        links = ", ".join(f"[{GUIDES[rules[s]['guide']].short}]({rules[s]['url']})"
                          for s in f.see_also)
        line += f"\n  - see also: {links}"
    return line


def shorten(s: str, n: int) -> str:
    s = norm_ws(s)
    if len(s) <= n:
        return s
    cut = s[: n - 1]
    if " " in cut[n // 2:]:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip(",;:") + "…"


def print_report_summary(run, rules, findings, unverified, skipped, rejected, out):
    sev = collections.Counter(f.severity for f in findings)
    print(f"report: {out}")
    print(f"findings: {len(findings)} (must {sev.get('must', 0)}, should "
          f"{sev.get('should', 0)}, consider {sev.get('consider', 0)}); "
          f"needs manual check: {len(unverified)}; rejected: {len(rejected)}")
    print(f"health: {health_line(run)}")
    print("most frequent rules:")
    for rid, n in collections.Counter(f.rule for f in findings).most_common(8):
        print(f"  {n:4d}  {rid}  {rules[rid]['url']}")
    # A ranked short list for the answer, so the full report need not be read:
    # every must, then reviewer findings (judgement, often real bugs) by
    # confidence, then the remaining should findings.
    must = [f for f in findings if f.severity == "must"]
    should = sorted((f for f in findings if f.severity == "should"),
                    key=lambda f: (f.source != "review", f.confidence != "high",
                                   rules[f.rule]["order"]))
    print("top findings for the answer:")
    for f in must[:15] + should[:12]:
        r = rules[f.rule]
        print(f"  [{f.severity}] {f.file}:{f.line} — {shorten(f.message, 170)} — "
              f"[{GUIDES[r['guide']].short} › {r['title']}]({r['url']})"
              + optional_mark(r))
    if len(must) > 15:
        print(f"  … {len(must) - 15} more must findings in the report")
    other = load_other_issues(run["run_dir"]) if len(run["guides"]) == 1 else []
    if other:
        print(f"linter issues under other guides (listed at the end of the report): "
              f"{len(other)}, e.g. " +
              "; ".join(f"{o['file']}:{o['line']} {shorten(o['message'], 60)}"
                        for o in other[:3]))
    if skipped:
        print(f"not reported, a higher-priority guide disagrees: {len(skipped)}")


# --------------------------------------------------------------------------
# validate / coverage


def enabled_linters() -> set[str]:
    """Linter and formatter names in the top-level enable lists of
    config/golangci.yml (linters.enable, formatters.enable). Nested enable lists,
    such as the analyzers of a linter's settings, are not linters."""
    names, section, in_enable = set(), None, False
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        top = re.match(r"^([a-z]+):", line)
        if top:
            section, in_enable = top.group(1), False
            continue
        if section in ("linters", "formatters") and re.match(r"^  enable:\s*$", line):
            in_enable = True
            continue
        if in_enable:
            m = re.match(r"^    - ([a-z0-9_-]+)", line)
            if m:
                names.add(m.group(1))
            elif line.strip() and not line.strip().startswith("#"):
                in_enable = False
    return names


# Analyzers go vet (and golangci-lint's govet) runs by default.
VET_DEFAULT = set("""appends asmdecl assign atomic bools buildtag cgocall composites copylocks
defers directive errorsas framepointer hostport httpresponse ifaceassert loopclosure lostcancel
nilfunc printf shift sigchanyzer slog stdmethods stdversion stringintconv structtag
testinggoroutine tests timeformat unmarshal unreachable unsafeptr unusedresult
waitgroup""".split())


def config_checks() -> dict[str, set[str]]:
    """The individual checks enabled in config/golangci.yml for the linters
    whose lint keys name a check. The config is ours, so a small reader of its
    layout is enough: `    <linter>:` sections with `      <key>:` lists."""
    lines = CONFIG.read_text(encoding="utf-8").splitlines()

    def section(name: str) -> list[str]:
        out, inside = [], False
        for line in lines:
            if re.match(rf"^    {re.escape(name)}:\s*$", line):
                inside = True
                continue
            if inside and re.match(r"^ {0,4}\S", line):
                break
            if inside:
                out.append(line)
        return out

    def items(sec: list[str], key: str) -> list[str]:
        out, inside = [], False
        for line in sec:
            if re.match(rf"^      {re.escape(key)}:\s*$", line):
                inside = True
                continue
            if inside:
                m = re.match(r"^        - (?:name: )?([A-Za-z0-9_-]+)", line)
                if m:
                    out.append(m.group(1))
                elif re.match(r"^ {0,6}\S", line):
                    inside = False
        return out

    checks = {
        "revive": set(items(section("revive"), "rules")),
        "gocritic": set(items(section("gocritic"), "enabled-checks")),
        "staticcheck": set(items(section("staticcheck"), "checks")),
        "gosec": set(items(section("gosec"), "includes")),
        "govet": VET_DEFAULT | set(items(section("govet"), "enable")),
    }
    modernize_all = {"any", "atomictypes", "embedlit", "errorsastype", "forvar",
                     "importcomment", "mapsloop", "minmax", "newexpr", "omitzero",
                     "plusbuild", "rangeint", "reflecttypeassert", "reflecttypefor",
                     "slicesbackward", "slicesclip", "slicescontains", "slicessort",
                     "stditerators", "stringsbuilder", "stringscut", "stringscutprefix",
                     "stringsseq", "testingcontext", "unsafefuncs", "waitgroupgo"}
    checks["modernize"] = modernize_all - set(items(section("modernize"), "disable"))
    return checks


def cmd_validate(args) -> None:
    problems: list[str] = []
    rules = load_rules(None, problems)
    anchors = anchor_tables()
    linters = enabled_linters() if CONFIG.exists() else set()
    checks = config_checks() if CONFIG.exists() else {}
    ids = collections.Counter(r.id for r in rules)
    for rid, n in ids.items():
        if n > 1:
            problems.append(f"duplicate rule id {rid}")
    for r in rules:
        where = f"{r.guide}/{r.topic_file}: {r.id}"
        if r.anchor not in anchors[r.guide]:
            problems.append(f"{where}: anchor not in _anchors.tsv")
        if r.severity not in SEVERITIES:
            problems.append(f"{where}: severity={r.severity!r}")
        if r.scope not in SCOPES:
            problems.append(f"{where}: scope={r.scope!r}")
        if r.check not in CHECKS:
            problems.append(f"{where}: check={r.check!r}")
        if "rule" not in r.bullets:
            problems.append(f"{where}: missing 'rule' bullet")
        if r.check in ("llm", "lint+llm") and "look for" not in r.bullets:
            problems.append(f"{where}: missing 'look for' bullet")
        if "lint" in r.check and not r.lint:
            problems.append(f"{where}: check={r.check} without lint keys")
        if r.check == "llm" and r.lint:
            problems.append(f"{where}: check=llm but lint keys given")
        for k in r.lint:
            if linters and k.linter not in linters:
                problems.append(f"{where}: lint key {k.raw!r}: linter not enabled in "
                                "config/golangci.yml")
            elif k.check and k.linter in checks and k.check not in checks[k.linter]:
                problems.append(f"{where}: lint key {k.raw!r}: check {k.check} is not "
                                "enabled in config/golangci.yml")
        for key in ("overlaps", "conflicts"):
            for ref in r.meta_list(key):
                g, _, a = ref.partition(":")
                a = a.split("/", 1)[0]
                if g not in GUIDES or a not in anchors.get(g, {}):
                    problems.append(f"{where}: {key} reference {ref!r} is not a known anchor")
                elif key == "overlaps" and GUIDES[g].priority >= GUIDES[r.guide].priority:
                    problems.append(f"{where}: overlaps {ref!r} is not a higher-priority guide")
        extra = set(r.meta) - {"severity", "scope", "check", "lint", "custom",
                               "overlaps", "conflicts"}
        if extra:
            problems.append(f"{where}: unknown meta keys {sorted(extra)}")
    by_guide = collections.Counter(r.guide for r in rules)
    for g in GUIDES:
        checks = collections.Counter(r.check for r in rules if r.guide == g)
        print(f"{g:17s} {by_guide.get(g, 0):3d} rules  " +
              "  ".join(f"{c}={checks.get(c, 0)}" for c in CHECKS))
    if problems:
        print(f"\n{len(problems)} problems:")
        for p in problems:
            print(f"  {p}")
        sys.exit(1)
    print("catalogs OK")


def cmd_coverage(args) -> None:
    rules = load_rules()
    out = ["# Coverage matrix", "",
           "Generated by `python3 skills/go-style/scripts/gostyle.py coverage` from the "
           "rule catalogs. `lint` — fully detected by the configured golangci-lint "
           "checks; `lint+llm` — linters detect part, the reviewer covers the rest; "
           "`llm` — reviewer only. `custom` — candidate for the planned analyzer suite "
           "(see linters-plan.md).", ""]
    out += ["| Guide | Rules | lint | lint+llm | llm | custom candidates |",
            "|---|---:|---:|---:|---:|---:|"]
    for g in GUIDES:
        rs = [r for r in rules if r.guide == g]
        c = collections.Counter(r.check for r in rs)
        cust = sum(1 for r in rs if r.meta.get("custom"))
        out.append(f"| {GUIDES[g].name} | {len(rs)} | {c.get('lint', 0)} | "
                   f"{c.get('lint+llm', 0)} | {c.get('llm', 0)} | {cust} |")
    out.append("")
    for g in GUIDES:
        rs = [r for r in rules if r.guide == g]
        if not rs:
            continue
        out += [f"## {GUIDES[g].name}", "",
                "| Rule | Sev | Scope | Check | Linter keys | Custom | Overlaps / conflicts |",
                "|---|---|---|---|---|---|---|"]
        for r in rs:
            rel = ", ".join(r.meta_list("overlaps"))
            if r.meta_list("conflicts"):
                rel += (" · " if rel else "") + "⚠ " + ", ".join(r.meta_list("conflicts"))
            keys = "<br>".join(f"`{k.raw.replace('|', chr(92) + '|')}`" for k in r.lint)
            out.append(f"| [{r.title}]({r.url}) | {r.severity} | {r.scope} | {r.check} | "
                       f"{keys} | {r.meta.get('custom', '')} | {rel} |")
        out.append("")
    print("\n".join(out))


# --------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(prog="gostyle", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare", help="resolve scope, run linters, write reviewer tasks")
    p.add_argument("targets", nargs="*", help="packages (./...), directories or .go files")
    p.add_argument("--guides", required=True,
                   help="comma-separated: " + ", ".join(GUIDES) + ", or all")
    p.add_argument("--diff", nargs="?", const="", default=None, metavar="BASE",
                   help="review only lines changed since BASE (default: merge-base with "
                        "the default branch, or uncommitted changes on it)")
    p.add_argument("--whole-files", action="store_true",
                   help="with --diff: report problems anywhere in the changed files")
    p.add_argument("--no-lint", action="store_true", help="skip golangci-lint")
    p.add_argument("--no-llm", action="store_true", help="linters only, no reviewer tasks")
    p.add_argument("--no-tests", action="store_true", help="leave _test.go files out")
    p.add_argument("--chunk-lines", type=int, default=CHUNK_LINES)
    p.add_argument("--single-task-lines", type=int, default=SINGLE_TASK_LINES)
    p.add_argument("--out", help="directory for runs (default <module>/.go-style)")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("report", help="merge findings and render the report")
    p.add_argument("--run", help="run directory (default: the latest run)")
    p.add_argument("--output", help="report path (default: reports/ next to the run's "
                   "runs/ directory, i.e. <module>/.go-style/reports/ unless prepare had --out)")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("validate", help="check the rule catalogs")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("coverage", help="print the coverage matrix as Markdown")
    p.set_defaults(func=cmd_coverage)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
