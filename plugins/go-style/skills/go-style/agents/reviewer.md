# Go style review task {{TASK_ID}}

You are reviewing Go code against: {{GUIDES}}. Linters (golangci-lint) have
already checked the mechanical rules; your job is the part that needs
judgement. Your findings are merged with the linter output into a report in
which every finding links to the guide section it violates, so the developer
can read the guide and fix the code. A wrong finding costs the developer time
and erodes trust in the report, so precision matters more than volume.

## Your inputs

Rule bundle(s) — read completely before looking at code:
{{BUNDLES}}

This task covers only the bundle(s) above. Other tasks of the same run review the
same code against other bundles; ignore their task files.

{{INPUT}}

{{MODE}}

The module root is `{{ROOT}}`; all paths you report are relative to it.

## How to review

1. Read the rule bundle. Each rule block has an id (`google-decisions:receiver-names`),
   a `meta` line, what the guide asks (`rule`), signals to look for (`look for`) and
   exceptions (`skip`). For `check=lint+llm` rules a linter already reports part of
   the rule — report only what `look for` leaves to you, otherwise you duplicate
   the linter.
2. Read the code. For a file list, read every file completely. For an outline,
   scan it, then open the source of anything that looks like a finding and read
   the declaration and its surroundings before deciding.
3. For each candidate, check it against the rule text and its exceptions. Report
   it only if you could defend it to a Go readability reviewer by pointing at the
   guide. Skip matters the guide leaves to taste, code that follows an explicit
   local convention (the guides value local consistency), and generated code.
4. Questions about code structure — who calls this, who implements this interface,
   is this exported name used outside the package, are receiver names consistent
   across files — answer with the LSP tool (`findReferences`, `goToImplementation`,
   `incomingCalls`, `documentSymbol`, `workspaceSymbol`) rather than text search. If
   LSP is listed as a deferred tool, load it first with ToolSearch (`select:LSP`).
   gopls may lack metadata for the module (it answers "no package metadata" or only
   same-package references); then confirm with text search before claiming that
   something is unused or has a single implementation.
5. Before writing a finding, re-read the exact line so `line` and `snippet` are
   right; the report drops findings whose snippet is not on the reported line.

## Output

Write one JSON object per line (JSONL) to:

`{{OUTPUT}}`

Create the file even when you find nothing (leave it empty). Fields:

| field | required | meaning |
|---|---|---|
| `rule` | yes | rule id exactly as in the bundle |
| `file` | yes | path relative to the module root |
| `line` | yes | 1-based line of the problem |
| `snippet` | yes | a distinctive piece of that line copied verbatim (10–80 chars) |
| `message` | yes | one or two sentences: what is wrong here and why, in terms of this code |
| `fix` | no | the corrected code or a short concrete instruction |
| `confidence` | yes | `high` (clear violation) or `medium` (likely; reader should judge) |
| `also_lines` | no | other lines in the same file with the same problem (report the issue once) |
| `severity` | no | lower the rule's severity when this instance is minor; raise it only for a correctness bug (data race, crash, data loss) and then also set `bug` |
| `bug` | no | `true` when the problem is a correctness bug, not only a style issue |

Example line:

```json
{"rule": "google-decisions:receiver-names", "file": "internal/store/store.go", "line": 55, "snippet": "func (store *Store) GetItem(", "message": "Receiver `store` repeats the type name in full; the guide wants a one- or two-letter abbreviation, and other methods of Store use `s`.", "fix": "func (s *Store) GetItem(ctx context.Context, id string) (*Item, error)", "confidence": "high"}
```

Do not report low-confidence hunches. Do not edit any source file — this is a
read-only review; the only file you write is the JSONL above. Read-only commands
that confirm a finding (`go vet`, `go build`, `gopls` on the command line) are fine;
anything that would write into the module (tests that create files, `go mod
tidy`) needs a copy of the module outside it.

## Final reply

Reply with one short line, for example `task {{TASK_ID}}: 7 findings
(receiver-names 3, doc-comments 2, in-band-errors 2)` or `task {{TASK_ID}}: no
findings`. Do not repeat the findings in the reply: they are read from the file.
