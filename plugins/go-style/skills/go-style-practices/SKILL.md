---
name: go-style-practices
description: Review Go code against the Google Go Style Best Practices (google.github.io/styleguide/go/best-practices): naming, package design, error structure and wrapping, documentation, declarations, option structs, test design, string building, global state and interfaces. golangci-lint plus reviewer subagents; every finding links to its best-practices section. Use when the user wants Google best-practice advice on Go code, APIs, errors or tests, or runs /go-style-practices.
compatibility: Needs the go-style skill (the shared engine) in the same skills directory — the go-style plugin ships both — plus go, python3 and golangci-lint v2.
argument-hint: "[./... | dirs | files] [--diff [base]] [--no-llm] [--no-tests]"
---

# Google Go Style Best Practices review

Best Practices is neither normative nor canonical: it collects patterns that
proved readable and robust at Google. Severities follow the document's own
wording (`should` where it is firm, `consider` for trade-offs, `must` only for
things package `testing` itself forbids), but present every finding as an
improvement with its trade-off, not as a violation.

## Run it

Read `${CLAUDE_SKILL_DIR}/../go-style/WORKFLOW.md` and follow it with
`ENGINE=${CLAUDE_SKILL_DIR}/../go-style`, `--guides google-practices` and the
user's arguments: `$ARGUMENTS`

Rule catalog: `${CLAUDE_SKILL_DIR}/../go-style/rules/google-practices/`
(naming, packages, errors, documentation, declarations, api-design, testing,
strings).

## When you summarize

Group the findings by theme (error handling, API design, tests) rather than by
file: best-practice advice usually calls for one decision applied across the
code, such as a consistent error-wrapping scheme or an option struct pattern.
