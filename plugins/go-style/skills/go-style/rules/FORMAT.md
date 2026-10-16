# Rule catalog format

Every guide has a directory here (`google-guide/`, `google-decisions/`,
`google-practices/`, `effective/`, `uber/`) with one Markdown file per topic.
The files are read by two consumers:

- **reviewer subagents** read the rule blocks as their checklist;
- **`scripts/gostyle.py`** parses them to map linter issues and LLM findings to a
  rule id, a guide link, a severity, and to build the per-run review bundles.

Files whose name starts with `_` (for example `_anchors.tsv`, the list of every
heading anchor in the guide) are data for validation and are not parsed as rules.

## Topic file

```markdown
# Google Style Decisions — Naming

One or two sentences: what this topic covers in the guide.

### google-decisions:receiver-names — Receiver names
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:receiver-naming
- **rule:** Receiver names are short (usually one or two letters), abbreviate the
  type, are identical across all methods of the type, and are never `this`/`self`.
- **look for:** receivers of three or more letters (`client *Client` -> `c`);
  names that do not abbreviate the type.
- **skip:** `this`/`self` and cross-method consistency — revive reports them.
- **example:** `func (tray Tray) Size()` -> `func (t Tray) Size()`
```

## Rule heading

`### <rule-id> — <title>` (an em dash surrounded by spaces).

`rule-id` is `<guide>:<anchor>`, optionally followed by `/<qualifier>` when one
guide section holds several separately checkable rules
(`uber:copy-slices-and-maps-at-boundaries/receiving`).

| guide              | link base                                                   |
|--------------------|-------------------------------------------------------------|
| `google-guide`     | `https://google.github.io/styleguide/go/guide#`             |
| `google-decisions` | `https://google.github.io/styleguide/go/decisions#`         |
| `google-practices` | `https://google.github.io/styleguide/go/best-practices#`    |
| `effective`        | `https://go.dev/doc/effective_go#`                          |
| `uber`             | `https://github.com/uber-go/guide/blob/master/style.md#`    |

The link of a rule is the link base plus the anchor (the qualifier is dropped).
The anchor must be one of the anchors in that guide's `_anchors.tsv` — copy it
exactly, including case (`effective:Getters`).

## The `meta` line

`- **meta:** key=value · key=value · …` (keys separated by ` · `).

| key         | values                         | meaning |
|-------------|--------------------------------|---------|
| `severity`  | `must` / `should` / `consider` | `must`: the guide states it as a requirement ("must", canonical rule, gofmt). `should`: normative default that admits justified exceptions. `consider`: advice, trade-off, or best practice. |
| `scope`     | `decl` / `body` / `test` / `repo` | Where a reviewer finds it. `decl`: visible in the declaration outline of `scripts/outline.go` — names, signatures, type and interface shapes, the first sentence of doc comments, import aliases and groups. `body`: needs the source itself — statements, full doc comment text, comment placement. `test`: anything in `_test.go` files. `repo`: package layout, package size and naming, global state, API shape across packages (reviewed with the outline). |
| `check`     | `lint` / `llm` / `lint+llm`    | `lint`: fully covered by the configured linters — reviewers skip it. `llm`: needs judgement — reviewers check it. `lint+llm`: linters cover part, the `look for` bullet says what is left for the reviewer. |
| `lint`      | comma-separated keys           | Linter issues that map to this rule. Key syntax: `linter`, `linter:check` (revive rule, staticcheck/gosec code, gocritic checker, govet analyzer), and an optional `~regex` matched against the issue text (`perfsprint~concatenation`). Required when `check` contains `lint`. |
| `custom`    | slug                           | Optional. A deterministic check no existing linter does, proposed for the custom analyzer suite (see `skills/docs/linters-plan.md` in the dev-env repository). Until it exists, the reviewer covers the rule. |
| `overlaps`  | comma-separated rule ids       | Optional. Rules of a **higher-priority** guide that cover the same concern. Both stay in the review (the lower-priority rule is often the more specific one); when both produce a finding on the same line, the report keeps the higher-priority one and links the other as "see also". |
| `conflicts` | comma-separated rule ids       | Optional. Rules or sections this one contradicts. Either side may record it. In a multi-guide run that includes both guides, the rule of the lower-priority guide is neither reviewed nor reported. A reference to a section without a rule of its own (e.g. `google-decisions:non-decisions`) counts too. In a single-guide run the report marks the findings as optional. |

Guide priority, highest first: `google-guide`, `google-decisions`,
`google-practices`, `effective`, `uber`.

## Body bullets

| bullet         | required             | content |
|----------------|----------------------|---------|
| `rule`         | yes                  | What the guide asks for, paraphrased faithfully and compactly, with the guide's own exceptions. Not a verbatim copy. |
| `look for`     | when `check` has llm | Concrete signals a reviewer can spot in code. |
| `skip`         | no                   | What not to report: exceptions from the guide, cases already covered by a linter, common false positives. |
| `example`      | no                   | A minimal bad -> good pair, one line each where possible. |
| `note`         | no                   | Context: where the guide is ambiguous, version caveats (e.g. advice made obsolete by a newer Go release). |
