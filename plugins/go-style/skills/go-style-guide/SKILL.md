---
name: go-style-guide
description: Review Go code against the core Google Go Style Guide (google.github.io/styleguide/go/guide): the canonical principles (clarity, simplicity, least mechanism, concision, maintainability, consistency) and core guidelines (formatting, MixedCaps, line length, naming). Finds hard-to-follow, over-engineered or inconsistent code and links each finding to the guide. Use for a principles-level Go readability review by Google's guide, or /go-style-guide.
compatibility: Needs the go-style skill (the shared engine) in the same skills directory — the go-style plugin ships both — plus go, python3 and golangci-lint v2.
argument-hint: "[./... | dirs | files] [--diff [base]] [--no-llm] [--no-tests]"
---

# Google Go Style Guide review

The Style Guide is the canonical and normative foundation of Google's Go style:
Style Decisions and Best Practices elaborate it. Most of it is principles, so
this review is mostly judgement — the linters add formatting, MixedCaps and
complexity hotspots (gocognit, nestif) that point reviewers at the code most
likely to violate simplicity and clarity.

## Run it

Read `${CLAUDE_SKILL_DIR}/../go-style/WORKFLOW.md` and follow it with
`ENGINE=${CLAUDE_SKILL_DIR}/../go-style`, `--guides google-guide` and the
user's arguments: `$ARGUMENTS`

Rule catalog: `${CLAUDE_SKILL_DIR}/../go-style/rules/google-guide/`
(principles, core).

## When you summarize

Principle findings are arguments, not mechanical violations. Present each with
its concrete cost (what a reader has to work out, what a maintainer could break)
and the simpler alternative, so the user can weigh it. The guide orders its
principles: clarity, simplicity, concision, maintainability, consistency — when
two findings pull in different directions, the earlier principle wins.
