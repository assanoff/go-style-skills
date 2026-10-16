---
name: go-style
description: Review Go code against all the canonical Go style guides at once — Google Go Style Guide, Google Style Decisions, Google Best Practices, Effective Go and the Uber Go Style Guide — with Google taking priority, each problem reported once and linked to the exact guide section. Runs golangci-lint for the mechanical rules (mapped to guide sections) and parallel reviewer subagents for the judgement rules, then writes a report. Use whenever the user wants Go code, a package, a module, or a branch/diff reviewed, audited or checked for idiomatic style, readability, naming, doc comments, error handling or Go best practices, even if no guide is named. For a single guide prefer go-style-guide, go-style-decisions, go-style-practices, go-style-effective or go-style-uber.
compatibility: Needs go, python3 and golangci-lint v2.14+ (git for --diff).
argument-hint: "[./... | dirs | files] [--diff [base]] [--guides list] [--no-llm] [--no-tests]"
---

# Go style review — all guides

Checks Go code against five guides in one run and reports every finding with a
link to the guide section it violates.

| priority | guide | `--guides` key | status |
|---|---|---|---|
| 1 | [Google Go Style Guide](https://google.github.io/styleguide/go/guide) | `google-guide` | canonical, normative |
| 2 | [Google Style Decisions](https://google.github.io/styleguide/go/decisions) | `google-decisions` | normative |
| 3 | [Google Best Practices](https://google.github.io/styleguide/go/best-practices) | `google-practices` | advisory |
| 4 | [Effective Go](https://go.dev/doc/effective_go) | `effective` | foundational, partly dated |
| 5 | [Uber Go Style Guide](https://github.com/uber-go/guide/blob/master/style.md) | `uber` | secondary |

## Run it

`ENGINE` is `${CLAUDE_SKILL_DIR}`. Read `${CLAUDE_SKILL_DIR}/WORKFLOW.md` and
follow it with `--guides all` — or the subset the user asked for, e.g.
`--guides google-decisions,uber` — and the user's arguments: `$ARGUMENTS`

## What the combined run adds

- One linter run and one set of reviewer tasks over merged rule bundles, which
  costs far less than running the five guide skills one after another.
- A concern covered by several guides is reviewed and reported once, under the
  highest-priority guide; the others appear as "see also" links.
- Advice that contradicts a higher-priority guide is not reported — for example
  Uber's 99-character line limit, the `_` prefix for unexported globals and
  `&T{}` over `new(T)` lose to Google; the report lists what was left out.

## Engine layout

This directory also hosts the engine the per-guide skills use:

- `WORKFLOW.md` — the steps every go-style skill follows
- `scripts/gostyle.py` — `prepare`, `report`, plus `validate` and `coverage` for maintainers
- `scripts/outline.go` — declaration outline of a module (standard library only)
- `config/golangci.yml` — golangci-lint v2 config; every check backs a guide rule
- `agents/reviewer.md` — instructions for the reviewer subagents
- `rules/<guide>/*.md` — rule catalogs, format in `rules/FORMAT.md`
