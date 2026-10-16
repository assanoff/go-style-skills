---
name: go-style-effective
description: Review Go code against Effective Go (go.dev/doc/effective_go): names (getters, -er interfaces, MixedCaps), control flow, multiple returns and defer, new vs make, composite literals, methods, interfaces and type assertions, the blank identifier, embedding, concurrency, errors, panic and recover. golangci-lint plus reviewer subagents; every finding links to the Effective Go section. Use when the user asks whether Go code is idiomatic per Effective Go, or runs /go-style-effective.
compatibility: Needs the go-style skill (the shared engine) in the same skills directory — the go-style plugin ships both — plus go, python3 and golangci-lint v2.
argument-hint: "[./... | dirs | files] [--diff [base]] [--no-llm] [--no-tests]"
---

# Effective Go review

Effective Go is the Go team's foundational guide to idiomatic Go. It was
written for Go's 2009 release and has been updated only lightly since, so some
advice predates generics, `errors.Is`/`errors.As`, Go 1.22 loop variables and
the `min`/`max` builtins — the rule catalog notes where newer Go changes the
advice, and reviewers judge code by today's Go.

## Run it

Read `${CLAUDE_SKILL_DIR}/../go-style/WORKFLOW.md` and follow it with
`ENGINE=${CLAUDE_SKILL_DIR}/../go-style`, `--guides effective` and the user's
arguments: `$ARGUMENTS`

Rule catalog: `${CLAUDE_SKILL_DIR}/../go-style/rules/effective/`
(names and formatting, control and functions, data and methods, interfaces and
embedding, concurrency and errors).

## When you summarize

Effective Go explains idioms by example. When a finding is about an idiom
(comma-ok, `switch` without condition, `defer` for cleanup), show the idiomatic
form next to the user's code — that teaches more than the rule name.
