# go-style review workflow

Shared by every go-style skill. The calling skill gives you `ENGINE` (this
directory), the guides to check (`--guides …`) and the user's arguments.

In the commands below `$ENGINE` stands for that directory: write the full path
in every command, since shell variables do not persist between commands.

The review has two halves. Deterministic rules are checked by golangci-lint and
mapped to guide sections by `scripts/gostyle.py`. Judgement rules are checked by
reviewer subagents, each reading one rule bundle and one slice of the code. The
script does all the bookkeeping, so you only orchestrate: prepare, spawn, report,
summarize.

## 1. Arguments

Targets: package patterns (`./...`, `./internal/...`), directories, or `.go`
files, relative to the current directory. Default: `./...` of the current
module. Flags:

| flag | meaning |
|---|---|
| `--diff [BASE]` | review only lines changed since BASE (default: merge-base with the default branch; on the default branch itself, the uncommitted changes) |
| `--whole-files` | with `--diff`: report problems anywhere in the changed files |
| `--no-llm` | linters only: fast, deterministic, no subagents |
| `--no-lint` | reviewers only (golangci-lint missing or unwanted) |
| `--no-tests` | leave `_test.go` files out |

Translate a request in words into these ("check my branch" → `--diff`, "only
the store package" → `./internal/store`). The calling skill fixes `--guides`;
only the combined `go-style` skill accepts a user-chosen subset. A topic focus
("errors and tests") does not narrow the run: review everything, then lead the
answer with those topics.

## 2. Prepare

Run from the user's working directory (inside the Go module):

```bash
python3 "$ENGINE/scripts/gostyle.py" prepare --guides <guides> [targets] [flags]
```

It prints the run directory, the scope, the linter summary, and the reviewer
tasks — one task file each. If it fails, show the error and stop (typical: not
inside a Go module). A missing golangci-lint is not fatal: the run continues
without linters and says so; tell the user (`go install
github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest`).

The linter config needs golangci-lint v2.14 or newer. Older releases reject it
(the linter run ends in an error such as `cannot find rule`) or, under a newer
Go release than they support, cannot load packages: the linter finds nothing
and the build errors point into the standard library. In either case suggest
the same `go install` command — it builds golangci-lint with the user's own Go.

## 3. Review with subagents

Skip this step when there are no tasks (`--no-llm`).

If there are more than 16 tasks and the user did not explicitly ask for a
complete audit, ask before spawning (AskUserQuestion): run all N tasks, only
non-test code (`--no-tests`), only a narrower path, or linters only. Each task is
one subagent reading a rule bundle and up to ~2500 lines of code. If you cannot
ask, run the report step for the linter findings, tell the user the size of the
review and how to start it, and stop.

Spawn one `general-purpose` subagent per task, in parallel, at most 10 per
message (a session runs about 20 subagents at once), in the foreground so the
batch returns when all of them are done. If your environment runs them in the
background anyway, wait for every completion notification before step 4. The
prompt is only:

> Read `<task_file>` and do exactly what it says. Reply with the one-line summary it asks for.

The task file holds the full reviewer instructions, so nothing else is needed,
and your own context stays small. A task usually takes a few minutes of work. If
a task has produced nothing after ~30 minutes, check whether it is still running
(the session may be queueing many agents); re-run it once if it died, or offer
the user the linter-only result (`report` works without reviewer findings). Do not review the code yourself meanwhile, and
do not read the findings files — the report step reads and verifies them. When a
batch returns, check that each task's output (`findings/<task-id>.jsonl` in the
run directory) exists; re-run a task once if it does not, telling the new
subagent to write `findings/<task-id>-r2.jsonl` instead (the report reads every
`.jsonl` there and folds duplicates, so a late original does no harm).

## 4. Report

```bash
python3 "$ENGINE/scripts/gostyle.py" report --run <run-dir printed by prepare>
```

It verifies each reviewer finding against the source — the quoted snippet must
be on the reported line — folds duplicates (the same problem from two linters,
or from several guides), applies the guide priority, writes the report into
the store in the home directory — `~/.go-style/reports/<module>/<timestamp>-style-<label>.md`
plus a `.json` twin, `$GO_STYLE_HOME` in place of `~/.go-style` when it is set —
and prints a summary: counts, a health line (linters, build, review tasks, issues
under other guides, git) and a ranked list of top findings for your answer.

If the store cannot be written (a sandbox that allows writes only in the
project), the script says so: run report again with
`--output <module root>/.go-style/report.md` and tell the user where it went.

## 5. Answer the user

In the user's language, short. Build it from the report summary; open the
report only for details you need:

- first, a direct answer to what the user asked ("how idiomatic is it?" gets a
  verdict), then the report path and counts by severity;
- the summary's top findings — every `must` and the ~10 most useful `should` —
  each as `path:line — message — [Guide › Section](url)`; explain in the user's
  language but quote linter messages verbatim (they are searchable as they are);
  merge entries that are plainly one problem, group several findings of one rule
  under one link, and keep code snippets to the two or three findings where they
  teach the most;
- findings marked "⚠ optional" (they contradict a higher-priority guide) apart,
  at the end;
- what limits the result, from the health line: linters missing or failing,
  type-check errors, review tasks without output, findings that need a manual
  check, linter issues under other guides (a single-guide report lists them at
  its end — point out real bugs among them);
- next steps: fix chosen findings; re-run with `--diff` after fixes (only when
  the health line does not say "not a git checkout"); `--no-llm` as a cheap
  regular check.

You may spot-check `must` findings against the source before relaying them; if a
finding looks wrong to you, say so rather than repeating it. Do not paste
the whole report. Do not modify the user's code during the review; fix only what
the user asks for after reading the report.

## Notes

- `.go-style/` is created in the module root with a `.gitignore` of `*`, so runs
  never show up in `git status`; reports are kept in the store, not there.
- Rule catalogs: `$ENGINE/rules/<guide>/*.md` (format: `rules/FORMAT.md`);
  linter config: `$ENGINE/config/golangci.yml`; reviewer template:
  `$ENGINE/agents/reviewer.md`.
- For a small scope (about 1500 lines or less) prepare plans one task per rule
  bundle, each reading all files, so the bundles are reviewed in parallel; larger
  scopes are split into declaration tasks (over an outline of all declarations),
  code tasks and test tasks.
