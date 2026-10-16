# Automating Go style review: research and design

This is the reasoning behind `skills/go-style*`: what the five guides ask for,
which part of it existing tools already check, what is left, and how the skills
cover the rest efficiently. The coverage numbers are in
[coverage.md](coverage.md) (generated from the rule catalogs); the plan for new
linters is in [linters-plan.md](linters-plan.md).

## 1. The guides

| Guide | Link | Status | Rule id prefix |
|---|---|---|---|
| Google Go Style Guide | <https://google.github.io/styleguide/go/guide> | canonical + normative | `google-guide:` |
| Google Style Decisions | <https://google.github.io/styleguide/go/decisions> | normative, not canonical | `google-decisions:` |
| Google Best Practices | <https://google.github.io/styleguide/go/best-practices> | neither (auxiliary) | `google-practices:` |
| Effective Go | <https://go.dev/doc/effective_go> | Go team's foundational guide, written for Go 1.0 and only lightly updated | `effective:` |
| Uber Go Style Guide | <https://github.com/uber-go/guide/blob/master/style.md> | company guide, opinionated | `uber:` |

**Priority**, as asked: Google first, Uber second. Inside Google the documents
rank themselves (the overview page defines canonical > normative > auxiliary).
Effective Go goes between Google and Uber: it is the Go team's own text and
Google's guide builds on it, but it predates generics, `errors.Is/As`, the Go
1.22 loop variables and so on, so where it is dated the newer guides win.

Every rule id is `<guide>:<anchor>`, where the anchor is the guide's real HTML
anchor, so the link in a report is derived from the id and cannot be
hallucinated. The anchor tables (`rules/<guide>/_anchors.tsv`) were extracted
from the guide sources: Google's Markdown has explicit `<a id>` tags (some
headings carry several — `naming` also answers to the stale `line-length`;
the extractor picks the id that matches the heading), Uber's anchors are
GitHub heading slugs (cross-checked against the guide's own table of contents:
all 65 TOC links match), Effective Go's are `id` attributes of its HTML.

All five texts are under Creative Commons attribution licenses, so the
catalogs paraphrase and link rather than copy.

## 2. Classifying every rule

Each actionable section of each guide became one rule (sometimes several, when
a section holds independently checkable requirements), classified by who can
detect a violation:

| check | meaning | who does it |
|---|---|---|
| `lint` | fully detected by a configured golangci-lint check | golangci-lint; the reviewer skips the rule |
| `lint+llm` | a linter detects part; the rule's `look for` says what is left | both |
| `llm` | needs judgement (naming quality, API shape, error strategy, goroutine lifetimes, test design, principles) | reviewer subagents |

plus an orthogonal `custom` tag: the violation is deterministic (decidable from
the AST and types) but no existing linter checks it — a candidate for the
planned analyzer suite. Until that exists the reviewer covers it.

The decision rule behind the classification:

1. **Already in the toolchain or golangci-lint → configure, never rewrite.**
   gofmt/goimports, `go vet` analyzers, staticcheck, revive, gocritic and ~25
   other linters in golangci-lint v2.14 cover a large share of the mechanical
   rules (see the table in §3). The skills ship one golangci-lint config in which
   every enabled check backs a guide rule.
2. **Deterministic but missing → a `go/analysis` analyzer** (planned, see
   linters-plan.md). Analyzers run in milliseconds, in CI, in the editor via
   gopls, with no LLM cost and no variance, and they are testable with
   `analysistest`.
3. **Needs judgement → the LLM review in the skills.** No linter can say that a
   name is unclear, that a goroutine has no owner, that an interface is defined
   on the wrong side, or that a function uses more mechanism than it needs.

### Why not Python or bash scripts that detect problems

Detection logic for Go belongs in Go. A regex over source text cannot tell a
type from a variable, a method on an exported type from one on an unexported
type, or a string literal from a comment; `go/ast` + `go/types` can, with the
same effort. So the scripts in the skills only do orchestration — scope,
running the linters, mapping, bundling rules, verifying and rendering — and the
one piece of code analysis they need (the declaration outline) is a small Go
program using only the standard library (`scripts/outline.go`).

### Why not ruleguard

go-ruleguard rules (run through gocritic inside golangci-lint) looked like the
cheapest way to add pattern rules without building a custom linter binary. It
does not work for this use: the rules file must import
`github.com/quasilyte/go-ruleguard/dsl`, and golangci-lint resolves that import
with the gc importer, which needs compiled export data of the dsl package.
Tried with golangci-lint v2.14 / Go 1.27: providing the package through a
`go.mod` next to the rules or through a private `GOPATH` both fail ("can't find
import" / "no such file … dsl.a"); it works only if the *audited* project
depends on the dsl module, which an audit tool cannot require. Analyzers built
on `go/analysis` have none of these problems.

## 3. Tool inventory (golangci-lint v2.14.0, Go 1.27)

Embedded versions: revive 1.17.0 (105 rules), staticcheck 2026.2.1 (149
checks), go-critic 0.15.0 (107 checkers), golang.org/x/tools 0.50.0 (vet
analyzers), plus the standalone linters. The checks that back guide rules:

| Area | Checks |
|---|---|
| formatting, imports | `gofmt` (simplify), `goimports` |
| naming | revive `var-naming`, `package-naming`, `receiver-naming` (max length 3), `exported` (stutter), `time-naming`; gocritic `captLocal`; `errname`; `predeclared`; `goprintffuncname` |
| doc comments | revive `exported`, `package-comments`; `godot`; godoclint `single-pkg-doc`; gocritic `docStub` |
| imports | revive `dot-imports`, `blank-imports`, `redundant-import-alias`, `import-alias-naming` |
| errors | staticcheck ST1005; revive `error-return`, `indent-error-flow`, `superfluous-else`, `early-return`; `errorlint`; `errcheck`; `nilerr`; `nilnil` |
| language | govet `composites`, `copylocks`, `printf`, `stdmethods`; revive `use-any`, `modifies-value-receiver`, `confusing-results`, `useless-break`, `range`, `var-declaration`, `enforce-map-style`, `enforce-slice-style`, `deep-exit`, `context-as-argument`; gocritic `sprintfQuotedString`, `switchTrue`, `ifElseChain`, `typeSwitchVar`, `ptrToRefParam`, `exitAfterDefer`, `typeDefFirst`; staticcheck S1009, S1023; `containedctx`; `forcetypeassert`; `recvcheck`; `nakedret`; `musttag`; `iface`; `interfacebloat`; `embeddedstructfieldcheck`; `funcorder`; `gochecknoglobals`; `gochecknoinits`; `perfsprint`; `prealloc`; `lll`; modernize `atomictypes` |
| tests | govet `testinggoroutine`; staticcheck SA2002; `thelper`; `tparallel`; `depguard` (assertion libraries in tests, cmp outside tests); `forbidigo` (`reflect.DeepEqual` in tests) |
| complexity hints | `gocognit`, `nestif` — hotspots for the principle review |

Deliberately **not** enabled, because they contradict a guide or measure taste
the guides do not share: `err113` (Uber explicitly allows inline
`errors.New`), `wrapcheck` (no guide requires wrapping everything),
`varnamelen` (Google ties name length to scope, not to a number),
`nonamedreturns` (both Google and Effective Go use named results),
`testpackage` (Google allows same-package tests), `paralleltest` (no guide
requires `t.Parallel`), `exhaustruct` (Uber says omit zero fields), `ireturn`
(iface `opaque` is the precise version of "return concrete types"),
`wsl`/`nlreturn`/`whitespace` (no guide rule), gosec G404 (flags every
`math/rand` call, while Google only forbids it for keys), revive `flag-parameter`,
`add-constant`, `function-length`, `cognitive-complexity` (numbers no guide
gives). Google's "Non-decisions" make `map{}` vs `make`, `&T{}` vs `new(T)` and
`errors.New` vs `fmt.Errorf` free choices, so those checks map only to Uber.

## 4. Skill design

### One engine, thin entry points

Six skills: one per guide as asked (`go-style-guide`, `go-style-decisions`,
`go-style-practices`, `go-style-effective`, `go-style-uber`) and the combined
`go-style`, which also hosts the shared engine. A guide skill is ~30 lines: what
the guide is, how to present its findings, and "follow the engine workflow with
`--guides <key>`". Everything that would otherwise be duplicated six times — the
workflow, the scripts, the linter config, the reviewer instructions and the rule
catalogs — lives once in `go-style/`.

Why not one mega-skill with all rules in its body: ~250 rules are far more than
a model can keep in focus while reading code, and loading them all into the
main conversation would crowd out the code itself. Why not five independent
skills: the rules overlap heavily (error strings, receiver names, panics…), and
five copies of the scripts and config would drift.

### The run

1. **prepare** (script): resolves the scope with `go list` (or the git diff),
   skips generated files, runs golangci-lint once with the shared config, maps
   every issue to a rule through the catalogs' `lint=` keys (one rule per guide),
   builds the *rule bundles* (only the `llm`/`lint+llm` rules of the selected
   guides, grouped into declaration / code / test bundles), the declaration
   outline, and one task file per reviewer subagent.
2. **review** (subagents, in parallel): each task is one subagent reading one
   rule bundle and one slice of the code, writing findings as JSONL with an
   exact rule id, file, line and a verbatim snippet.
3. **report** (script): verifies every reviewer finding (the snippet must be on
   the reported line; the line is corrected when the snippet is found nearby;
   unconfirmed findings go to a "needs a manual check" section), removes
   duplicates (linter copy wins), applies guide priority, renders Markdown + JSON.

### Why it is efficient

- **The model never re-checks what a linter decided.** `check=lint` rules are
  not in the bundles at all; `lint+llm` rules tell the reviewer exactly what is
  left.
- **Declaration rules are reviewed on an outline**, not on the code: names,
  signatures, doc comment first sentences, type and interface shapes and package
  structure of a whole module fit in a fraction of its source. Code and test
  rules go to chunks of ~2500 lines; a scope under ~1500 lines gets one task per
  rule bundle, each reading all files, so the bundles are reviewed in parallel.
- **The orchestrator's context stays small**: a task prompt is one line pointing
  to a task file, a subagent answers with one line, findings travel through
  files, and the script — not the model — merges and verifies them.
- **Links are deterministic**: reviewers cite rule ids; the script turns them
  into URLs from the catalog.
- **Combined runs resolve guide disagreements before reviewing**: a rule that
  contradicts a higher-priority guide (`conflicts=`, recorded on either side) is
  left out of the bundles and never reported. Rules that merely overlap stay in —
  the lower-priority guide is often the more specific one (Decisions elaborates
  the Guide) — and the report folds findings that land on the same line into
  one entry under the higher-priority guide, with "see also" links; one linter
  issue that maps to rules of several guides becomes one entry the same way.

### Guide conflicts

Where Uber contradicts Google, Google wins in combined runs and the per-guide
Uber report flags the finding as optional:

| Uber | Google |
|---|---|
| soft line limit of 99 characters | no line length limit; do not break lines just for length |
| prefix unexported globals with `_` | no underscores in names |
| table tests written with testify `assert`/`require` | only the `testing` package (+ `cmp`); no assertion libraries |

(The list in the catalogs is the source of truth — search for `conflicts=`.)

## 5. Evaluation

`skills/evals/fixture` is a small module (store, notifier, util package, main;
414 lines) with seeded problems across the guides; `expected.json` lists them
(rule ids that count as a hit, a line, `optional` for debatable ones) and
`score.py` computes recall per guide from a report's JSON twin and lists every
finding that matches nothing, for manual review. Each skill was run by a
subagent following the skill exactly (spawning its own reviewer subagents); the
baseline was the same model with the same request and no skill — it could read
the guides, run any tools, and was told the anchor format so it could be scored.

Iteration 1 (one reviewer task per run for small scopes), recall on the items
relevant to each run's guides:

| Run | With skill | Baseline (no skill) |
|---|---|---|
| Google Decisions | 36/37 (97%) | 36/37 (97%) |
| Uber | 26/26 (100%) | 24/26 (92%) |
| All five guides | 56/59 (95%) | 56/60 (93%) |
| Effective Go | 15/17 (88%; the 2 misses were a mapping gap, fixed) | — |
| Google Best Practices | 8/10 (80%) | — |
| Google Style Guide (`./pkg/... ./internal/...`) | 3/3 in scope | — |

What the numbers say, honestly:

- On a 400-line module a strong model without the skill finds about as much:
  it reads every line, and the baselines even ran golangci-lint, vet and gopls on
  their own. The skill matched or beat it on every run, with fewer nits in the
  report (2–13 findings outside the seeded set per run, nearly all real issues,
  against 8–25 for the baselines, several of them catch-alls).
- The skill's real advantages are the ones a small fixture cannot show by recall:
  every link is derived from a rule id (the baselines chose between alias anchors
  on their own); the mechanical half is complete and deterministic instead of
  depending on whether the model thinks of running a linter; Google-over-Uber
  conflicts are resolved by rule, not ad hoc; and the work is split so it scales
  past what one context can read — a real diff of 7 files / 1,700 lines in the
  ghq repository planned 5 parallel tasks in 10 seconds.
- Iteration 1 was slow on small scopes: the single reviewer read all bundles in
  series (11–19 minutes of work per run). Iteration 2 gives each bundle its own
  parallel task: on the same fixture the three Decisions reviewers worked 1–5.5
  minutes each (recall 35/37: one miss was a report-folding bug, fixed
  afterwards; the other, `os.Exit` inside a `Must…` helper, was missed by every
  run, with or without the skill). Their wall-clock time in that run was ~80 minutes, but almost all
  of it was queueing behind the other evaluation agents running in the session
  at the same time, not work.

A real diff: `--diff HEAD~30` on the ghq repository (7 changed files, 1,700
lines, all five guides) planned 5 parallel tasks, kept every linter finding on
changed lines, dropped Uber's 16 line-length findings for Google's priority, and
produced 54 findings. Among them were a real bug (with `--parallel` a failed
clone's result is still stored and used), a data race in an errgroup, a context
added to a signature but never used, and a test that passes for the wrong reason
(flagged for a manual check because it sits just outside the changed lines).
The evaluator checked all 55 entries against the code: about 38 real (17 clearly
useful), about 17 noise — mostly `errcheck` on `fmt.Fprintf` to a CLI writer,
`thelper` on scenario callbacks, inflated complexity scores in tests and two
near-duplicates. The first and third are excluded now (std-error-handling preset,
no gocognit in tests) and near-line duplicates of overlapping rules are folded.

The evaluators' reports drove these changes after iteration 1: parallel tasks
per bundle; folding one problem reported by two linters on nearby lines, or by a
linter and a reviewer; listing linter issues that belong to guides outside a
single-guide run (one was a real `t.Fatal`-in-goroutine bug); a health line and
a ranked top-findings list in the report summary; plain gofmt instead of
`gofmt -s` for the canonical formatting rule; the std-error-handling exclusion
(deferred `Close`); explicit waiting, stall and re-run instructions in the
workflow; changed-line ranges for the outline tasks of a diff review; reviewers
may raise the severity of a finding that is a correctness bug (`bug: true`).

## 6. Limitations

- The review needs the code to build for type-aware linters; type-check errors
  are reported and reduce coverage.
- The LLM part is not deterministic: two runs can differ in borderline findings.
  Verification removes findings with wrong locations, not wrong judgement.
- Multi-module repositories: one module per run (the module of the current
  directory).
- Rules that need history (e.g. "was this exported name renamed?") or runtime
  data (performance advice) are reviewed as code smells only.
