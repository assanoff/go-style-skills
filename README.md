# go-style-skills

[![validate](https://github.com/assanoff/go-style-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/assanoff/go-style-skills/actions/workflows/validate.yml)

Claude Code skills that review Go code against the canonical Go style guides —
the Google Go Style Guide, Google Style Decisions, Google Best Practices,
Effective Go and the Uber Go Style Guide. Every finding in the report links to
the exact guide section it violates, so you can read the guide and fix the code.

golangci-lint checks the mechanical rules with a config in which every check
backs a guide rule; reviewer subagents check the rules that need judgement
(names, API shape, error strategy, goroutine lifetimes, test design, principles).

## Install

In Claude Code:

```text
/plugin marketplace add assanoff/go-style-skills
/plugin install go-style@go-style-skills
```

On Claude Code 2.1.275 or later one line does both:

```text
/plugin install go-style --marketplace assanoff/go-style-skills
```

From the shell: `claude plugin marketplace add assanoff/go-style-skills`, then
`claude plugin install go-style@go-style-skills`. Restart Claude Code or run
`/reload-plugins` afterwards; `/plugin` lists the installed plugin.

**Update.** Auto-update is off for third-party marketplaces: run
`claude plugin update go-style`, or turn on auto-update for `go-style-skills`
under `/plugin` → Marketplaces.

### Requirements

- `go` and the Go module you want to review
- `python3` 3.9 or newer (standard library only)
- [golangci-lint](https://golangci-lint.run) **v2.14 or newer** — older releases
  reject the config or cannot load packages of Go 1.27. Install it with your own
  Go, so it always supports your Go version:
  `go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest`.
  Without golangci-lint the run continues with the review only.
- `git` for `--diff`

## Skills

| Skill | Checks against | Typical use |
|---|---|---|
| `/go-style:go-style` | all five guides, Google first, each problem once | the default: "review this module / my branch" |
| `/go-style:go-style-guide` | [Google Style Guide](https://google.github.io/styleguide/go/guide) — principles, core guidelines | is this code clear, simple, maintainable? |
| `/go-style:go-style-decisions` | [Google Style Decisions](https://google.github.io/styleguide/go/decisions) | naming, doc comments, errors, language, tests |
| `/go-style:go-style-practices` | [Google Best Practices](https://google.github.io/styleguide/go/best-practices) | API, package and test design advice |
| `/go-style:go-style-effective` | [Effective Go](https://go.dev/doc/effective_go) | idiomatic Go |
| `/go-style:go-style-uber` | [Uber Go Style Guide](https://github.com/uber-go/guide/blob/master/style.md) | Uber's guidelines, conflicts with Google flagged |

Plugin skills carry the plugin name as a prefix (`go-style:`). Plain requests
work too — "review my branch against the Uber guide" picks the right skill.

## Use

Run it from inside the Go module:

```text
/go-style:go-style                         whole module of the current directory
/go-style:go-style ./internal/store/...    a subtree
/go-style:go-style --diff                  only lines changed against the default branch
/go-style:go-style --diff origin/release   … against another base
/go-style:go-style-decisions --no-llm      linters only: seconds, no subagents
/go-style:go-style --guides google-decisions,uber --no-tests
```

| Flag | Meaning |
|---|---|
| `--diff [BASE]` | review only lines changed since BASE (default: merge-base with the default branch) |
| `--whole-files` | with `--diff`: report problems anywhere in the changed files |
| `--no-llm` | linters only: fast, deterministic, no subagents |
| `--no-lint` | reviewers only |
| `--no-tests` | leave `_test.go` files out |
| `--guides LIST` | `/go-style:go-style` only: a subset of `google-guide`, `google-decisions`, `google-practices`, `effective`, `uber` |

The report goes to `~/.go-style/reports/<module>/<time>-style-<guides>.md` with a
`.json` twin: the reports of all your modules in one place and none in the
repository; `GO_STYLE_HOME` moves the store. The working files of a run stay in
`<module>/.go-style/runs/`, and `.go-style/` carries its own `.gitignore`, so it
never shows up in `git status`. [go-audit](https://github.com/assanoff/cmd/tree/master/go-audit)
lists the store (`go-audit reports`) and keeps its own reports there; its
[package doc](https://github.com/assanoff/cmd/blob/master/go-audit/doc.go)
describes the layout and the JSON fields every report has.

Claude answers with a summary: counts by severity, the top
findings with their guide links, and what limited the run. The skills never
change your code; fix what you choose after reading the report.

A large scope is split into many reviewer tasks; above 16 Claude asks before
starting them. For a first run on a big repository, `--diff`, one package or
`--no-llm` is a good start.

## How it works

```text
prepare (script)          review (subagents, parallel)       report (script)
─────────────────         ──────────────────────────────      ─────────────────────────
go list / git diff   ──►  task = rule bundle + code slice ──► verify snippet on the line
golangci-lint, mapped     declarations: on an outline         dedupe, guide priority
rule bundles, outline     code, tests: ~2500-line chunks      Markdown + JSON with links
task files                findings → JSONL                    summary for the chat
```

- Mechanical rules are checked by golangci-lint with
  [`config/golangci.yml`](plugins/go-style/skills/go-style/config/golangci.yml),
  where every enabled check backs a guide rule; the script maps each issue to
  the rule and its link. It is a style config, not an audit: issues that back no
  guide rule are dropped.
- Judgement rules are checked by reviewer subagents, each reading one rule
  bundle and one slice of the code; the model never re-checks what a linter
  decided.
- A reviewer finding is kept only if the code it quotes is found on (or next to)
  the reported line.
- Links are built from rule ids (`<guide>:<anchor>`), never written by the model.
- In a combined run a concern covered by several guides is reported once, under
  the highest-priority guide (Google Guide, Decisions, Best Practices, Effective
  Go, Uber), and advice that contradicts a higher-priority guide — such as Uber's
  99-character line limit — is left out.

Details and the reasoning behind every choice: [docs/research.md](docs/research.md).
What is covered by what: [docs/coverage.md](docs/coverage.md). Planned analyzers
for rules no linter checks yet: [docs/linters-plan.md](docs/linters-plan.md).

## Without the plugin

The six skill directories in [`plugins/go-style/skills/`](plugins/go-style/skills/)
also work as plain skills. Copy or symlink **all six** into `~/.claude/skills/` —
the per-guide skills use the engine in `go-style/` next to them — and call them
without the prefix (`/go-style`, `/go-style-uber`).

Other agents that read `~/.agents/skills` can load the same directories, but the
skills are written for Claude Code (`${CLAUDE_SKILL_DIR}`, `$ARGUMENTS`,
subagents). The part that works anywhere is the linter-only run of the script:

```bash
G=path/to/plugins/go-style/skills/go-style/scripts/gostyle.py
python3 $G prepare --guides all --no-llm    # inside the Go module
python3 $G report                           # report of the latest run, into the store
```

## Layout

```text
.claude-plugin/marketplace.json     the go-style-skills marketplace
plugins/go-style/                   the plugin users install
  .claude-plugin/plugin.json        name, version, metadata
  skills/go-style/                  combined skill + the shared engine
    SKILL.md  WORKFLOW.md           entry point; the steps every go-style skill follows
    scripts/gostyle.py              prepare | report | validate | coverage
    scripts/outline.go              declaration outline (standard library only)
    config/golangci.yml             golangci-lint v2 config, every check backs a rule
    agents/reviewer.md              reviewer subagent instructions (template)
    rules/<guide>/*.md              rule catalogs, one file per topic; rules/FORMAT.md
  skills/go-style-{guide,decisions,practices,effective,uber}/SKILL.md   thin entry points
  LICENSE  NOTICE  LICENSES/        copies of the files at the repository root
docs/                               research, coverage matrix, analyzer plan
evals/                              fixture module with seeded problems, expected.json, score.py, tests
tools/                              check-fixture, refresh-anchors, anchors.py
```

## Development

```bash
E=plugins/go-style/skills/go-style
python3 $E/scripts/gostyle.py validate                  # catalogs: format, anchors, lint keys
python3 evals/test_gostyle.py                           # unit tests of gostyle.py
python3 evals/test_score.py                             # unit tests of score.py
tools/check-fixture                                     # linter-only run on the fixture, scored
python3 $E/scripts/gostyle.py coverage > docs/coverage.md
tools/refresh-anchors --dry                             # did a guide change its headings?
claude plugin validate . --strict                       # marketplace and plugin manifests
```

CI ([`.github/workflows/validate.yml`](.github/workflows/validate.yml)) runs all
of these except `refresh-anchors` and `coverage`, with golangci-lint v2.14.0 and
Go 1.27.

To add or change a rule, edit the topic file in `$E/rules/<guide>/` following
[`rules/FORMAT.md`](plugins/go-style/skills/go-style/rules/FORMAT.md), then run
`validate`. To back a rule with a new linter check, enable the check in
`config/golangci.yml` and add its key to the rule's `lint=`.

To measure the skills, run one on a copy of `evals/fixture` and score the report:
`python3 evals/score.py <report>.json` (recall per guide, unexpected findings).

To try local changes as a plugin: `claude plugin marketplace add <path to this
repository>`, then install `go-style@go-style-skills` from it. For a release,
bump `version` in `plugins/go-style/.claude-plugin/plugin.json` and add an entry
to [CHANGELOG.md](CHANGELOG.md); installed copies update only when the version
changes.

## License

MIT, see [LICENSE](LICENSE). The rule catalogs are adapted from the style
guides — Google Go Style Guide (CC BY 3.0), Effective Go (CC BY 4.0) and the
Uber Go Style Guide (Apache-2.0); attribution and details are in
[NOTICE](NOTICE). This project is not affiliated with or endorsed by Google,
Uber or the Go team.
