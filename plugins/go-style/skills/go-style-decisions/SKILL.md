---
name: go-style-decisions
description: Review Go code or a diff against the Google Go Style Decisions (google.github.io/styleguide/go/decisions): naming, doc comments, imports, error handling, language usage, contexts and tests. golangci-lint covers the mechanical rules, reviewer subagents the rest; the report links every finding to its decisions section. Use when the user asks to check Go code against Google's style decisions or Google readability rules, or runs /go-style-decisions.
compatibility: Needs the go-style skill (shared engine) in the same skills directory, plus go, python3 and golangci-lint v2.
argument-hint: "[./... | dirs | files] [--diff [base]] [--no-llm] [--no-tests]"
---

# Google Go Style Decisions review

Style Decisions is normative but not canonical: it records Google's settled
choices on specific style points and the reasoning behind them. Findings default
to `should`; `must` is used only where the document says must.

## Run it

Read `${CLAUDE_SKILL_DIR}/../go-style/WORKFLOW.md` and follow it with
`ENGINE=${CLAUDE_SKILL_DIR}/../go-style`, `--guides google-decisions` and the
user's arguments: `$ARGUMENTS`

Rule catalog: `${CLAUDE_SKILL_DIR}/../go-style/rules/google-decisions/`
(naming, commentary, imports, errors, language, libraries, testing).

## When you summarize

- The testing rules are strict about assertion libraries (testify and the like).
  If the project uses one throughout, say so once, as a project-level decision
  for the user, instead of listing every test file.
- Naming findings are cheapest to fix while the code is fresh; point out the ones
  in exported API first, since renaming them later breaks callers.
