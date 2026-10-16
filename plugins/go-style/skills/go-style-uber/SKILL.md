---
name: go-style-uber
description: Review Go code against the Uber Go Style Guide (github.com/uber-go/guide): interfaces, mutexes, copying at boundaries, channel sizes, enums, time, errors (types, wrapping, handle once), globals, init, exit, goroutines, performance, style and patterns (table tests, functional options). golangci-lint plus reviewer subagents; each finding links to the Uber section, and advice that contradicts Google's guides is flagged. Use when the user asks to check Go code against Uber's guide, or runs /go-style-uber.
compatibility: Needs the go-style skill (the shared engine) in the same skills directory — the go-style plugin ships both — plus go, python3 and golangci-lint v2.
argument-hint: "[./... | dirs | files] [--diff [base]] [--no-llm] [--no-tests]"
---

# Uber Go Style Guide review

The Uber guide is more opinionated than Google's and ranks below it here.
Severities follow its wording: `must` where it says must or always (handling
type-assertion failures, goroutine lifetimes, no panics in production code),
`should` for most guidelines, `consider` for performance and taste.

Where Uber contradicts a higher-priority guide, the report marks the finding as
optional and the combined `go-style` skill drops it. The recorded conflicts
include the 99-character line limit, the `_` prefix for unexported globals,
`/* name */` comments on bare arguments, `&T{}` over `new(T)`, two import groups,
`%w` as the default wrapping verb, capacity hints by default, and Uber's stricter
stance on `panic` and `os.Exit` outside `main` (search the catalog for
`conflicts=` for the full list).

## Run it

Read `${CLAUDE_SKILL_DIR}/../go-style/WORKFLOW.md` and follow it with
`ENGINE=${CLAUDE_SKILL_DIR}/../go-style`, `--guides uber` and the user's
arguments: `$ARGUMENTS`

Rule catalog: `${CLAUDE_SKILL_DIR}/../go-style/rules/uber/`
(guidelines, errors, globals and lifecycle, performance, style, patterns).

## When you summarize

Mention conflicting findings separately at the end, so the user can decide
whether the project follows Uber or Google on those points. When a finding rests
on dated advice, say so in that finding: `go.uber.org/atomic` is superseded by
the typed values in `sync/atomic` (Go 1.19+), and copying loop variables for
parallel tests is unnecessary since Go 1.22.
