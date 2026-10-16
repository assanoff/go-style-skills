# Plan: custom analyzers for the rules no linter checks

Status: **planned**. The skills already cover these rules through the reviewer
subagents; an analyzer moves a rule from "the model looks for it" to "a tool
finds every instance in milliseconds", which is cheaper, deterministic, runs in
CI and in the editor, and frees the reviewer for judgement.

## What qualifies

A rule gets an analyzer only when all of these hold:

1. **No existing check does it.** golangci-lint v2.14 ships ~110 linters plus
   ~100 revive rules, ~100 gocritic checkers and ~150 staticcheck checks; the
   catalogs already map those (`lint=` keys). Before writing an analyzer, check
   again — linters gain checks every release.
2. **Deterministic from syntax and types.** The violation can be decided from
   `go/ast` + `go/types` (and, at most, facts across packages), without knowing
   intent.
3. **Low false-positive rate.** Below roughly one false positive in ten reports
   on real code; otherwise people learn to ignore it, and the reviewer (which can
   weigh context) is the better place.
4. **Worth it.** The rule is violated often enough, or the violation is costly
   enough, to justify code plus tests.

The catalogs tag 111 candidate checks with `custom=<slug>` (list:
`python3 plugins/go-style/skills/go-style/scripts/gostyle.py coverage`). The curated set below
merges overlapping slugs, drops those an existing linter already covers, and
leaves the heuristic ones to the reviewer.

## Packaging

One Go module, `gostylelint` (its own repository, like the user's other Go
commands), built only on `golang.org/x/tools/go/analysis`:

```text
gostylelint/
  analyzers/<name>/<name>.go        one package per analyzer: var Analyzer *analysis.Analyzer
  analyzers/<name>/<name>_test.go   analysistest.Run over testdata/src/<case>/
  analyzers/<name>/testdata/src/... positive and negative cases with // want "…" comments
  cmd/gostylelint/main.go           multichecker.Main(analyzers.All...)
  plugin/plugin.go                  golangci-lint module plugin (register.Plugin)
```

- **Standalone**: `go install …/cmd/gostylelint@latest`; runs as
  `gostylelint ./...` or `go vet -vettool=$(which gostylelint) ./...`; `-json`
  output; suggested fixes via `-fix` where safe.
- **golangci-lint**: through the module plugin system — a `.custom-gcl.yml`
  naming the module, `golangci-lint custom` builds a binary with the plugin, and
  the plugin's checks become ordinary linters with settings in `.golangci.yml`.
- **Messages carry the rule id** (`[uber:channel-size-is-one-or-none] channel
  buffer of 100; use 0 or 1`), so CI output already links to the guide.
- **In the skills**: `gostyle.py prepare` runs `gostylelint -json` when it is on
  `PATH`; the catalog rule gets `lint=gostylelint:<analyzer>` and its `check`
  moves from `llm` to `lint+llm` or `lint` — the reviewer stops spending tokens
  on it. `gostyle.py validate` and `coverage` show the progress.

Each analyzer is small: an `inspector` pass over the relevant node types, type
checks via `pass.TypesInfo`, a report with the position of the offending node.
Tests come first: the guide's own Bad/Good examples are the first test cases.

## Rollout

1. Write the analyzer with `analysistest` cases (the guide's examples, plus the
   false positives listed in the rule's `skip` bullet).
2. Run it on a corpus — this repository's Go projects, `golang.org/x/tools`,
   a couple of popular modules — and read every report; tighten until the
   false-positive bar holds.
3. Add the `lint=` key to the catalog rule, change `check`, run `validate`.
4. Enable it in `go-style/config/golangci.yml` (or the standalone run).

## Analyzers

The curated list is in the next section, ordered by priority. P1: precise and
frequently useful — write first. P2: precise but narrower, or needing more
code. P3: useful heuristics with a known false-positive risk — prototype,
measure, keep only if they pass the bar.

### P1 — write first

| Analyzer | Checks | Rules | Detection | FP risk |
|---|---|---|---|---|
| `getterprefix` | `Get`/`get` prefix | google-decisions:getters, google-practices:function-name-conventions/get-prefix, effective:Getters | func/method named `Get[A-Z0-9]…` that returns a value; skip methods required by an interface from another package (check with `types.Implements` against the interfaces of imported packages), HTTP-GET-ish names (`GetRequest`, receivers of HTTP clients) | medium → mitigated by the exclusions |
| `chanbuf` | buffered channel size | uber:channel-size-is-one-or-none | `make(chan T, N)` with a constant N > 1 | low |
| `enumzero` | enum starting at zero | uber:start-enums-at-one | typed `const` block whose first spec is `= iota` (not `iota + 1`, not `1 << iota`), unless the first name says unknown/unspecified/invalid/none/default/zero | low–medium |
| `testmsg` | test failure messages | google-decisions:got-before-want, google-decisions:print-diffs, google-decisions:identify-the-function | in `t.Errorf/Fatalf/Logf` format literals: want/expected before got/actual; "expected/actual" wording; a printed `cmp.Diff(a, b)` whose direction key contradicts the argument names (`(-want +got)` with `cmp.Diff(got, want)`); no `\n` before a diff; formats starting with `got`/`want` and naming no call | low |
| `handleonce` | log and return the same error | uber:handle-errors-once, google-practices:error-logging/duplication | inside one block: a call to a logger (std `log`, `slog`, configurable list: zap, logrus, zerolog) with `err` among its arguments, then `return` of `err` or of a `fmt.Errorf` wrapping it | medium (boundaries that return a sanitized error); configurable |
| `panicerr` | panic for ordinary errors | google-decisions:dont-panic, uber:dont-panic/production | `panic(err)` / `panic(fmt.Sprintf(… err …))` under `if err != nil` in a function that is not `main`, `init`, a `Must…` function or a test | low–medium |
| `mainexit` | exit discipline in `main` and `init` | uber:exit-once, uber:no-goroutines-in-init | more than one `os.Exit`/`log.Fatal*` call in `main`; a `go` statement inside `func init()` | low |
| `mutexzero` | mutex pointers | uber:zero-value-mutexes-are-valid/pointer, google-practices:vardeclzero/uncopyable | fields or variables of type `*sync.Mutex`/`*sync.RWMutex`; `new(sync.Mutex)`, `&sync.Mutex{}` | low |
| `errstring` | matching on error text | google-practices:error-structure/string-matching, uber:error-types/matching, google-decisions:test-error-semantics/strings | `err.Error()` (or `fmt.Sprint(err)`) as operand of `==`/`!=`, `strings.Contains/HasPrefix/HasSuffix/Index`, `regexp` matching, or a `switch` tag | low (test files: report as the test rule; property checks on own messages are allowed — keep `strings.Contains` in tests at low confidence) |
| `rawstring` | escaped quotes | uber:use-raw-string-literals-to-avoid-escaping | interpreted string literal with ≥ 2 `\"` or `\\` escapes, no other escapes, no backquote — a raw string can express it | low |
| `elseassign` | assignment in both branches | uber:unnecessary-else | `if c { x = a } else { x = b }` (each branch a single assignment to the same variable, no `else if`) right after `var x T` or with `x` declared just above | low |
| `namerepeat` | names repeating their context | google-decisions:repetitive-with-package, google-decisions:repetitive-in-context, google-practices:function-name-repetition | exported name containing the package name anywhere but the prefix (revive covers the prefix: `widget.NewWidget`); method name starting with its receiver's type name (`(p *Project) ProjectName`) | low–medium |

### P2 — precise but narrower or more work

| Analyzer | Rules | Detection | FP risk |
|---|---|---|---|
| `literals` | uber:omit-zero-value-fields-in-structs, google-decisions:literal-zero-value-fields, uber:use-var-for-zero-value-structs, google-practices:vardeclzero, uber:use-field-names-to-initialize-structs, google-practices:t-field-names | keyed fields set to `""`, `0`, `false`, `nil` outside test tables; `x := T{}` for a struct `T`; positional literals of package-local structs with ≥ 4 fields or adjacent same-typed fields (test tables: Uber allows ≤ 3 fields) | medium (sub-checks individually switchable) |
| `boundarycopy` | uber:copy-slices-and-maps-at-boundaries | exported method assigning a slice/map parameter directly to a receiver field; exported method returning a slice/map field of its receiver, especially while holding the receiver's mutex | medium |
| `typeinname` | google-decisions:repetitive-with-type | local whose name ends in a type word matching its actual type (`nameString string`, `usersMap map…`, `itemsSlice []…`, `countInt int`), unless the stripped name is also declared in the scope (`limitStr` + `limit`) | low–medium |
| `chandir` | google-practices:decl-chan | `chan T` parameter or result only received from, or only sent on and closed, inside the function | low |
| `ptrparam` | google-decisions:pass-values | `*string`/`*int`/`*bool`/small-struct pointer parameter never written through, never stored, never compared to nil | low–medium |
| `mustcall` | google-decisions:must-functions | `Must…`/`template.Must` call with non-constant arguments inside a function that returns `error` (it should propagate the error) | low–medium |
| `errorfmt` | google-practices:error-percent-w, google-practices:error-percent-w-sentinel-placement, google-practices:error-extra-info, uber:error-wrapping/context | `%w` not at the end of the format (`"…: %w"`) for non-sentinel errors; sentinels not first; annotations that add nothing (`"error: %w"`, `"failed: %w"`); `"failed to …"` prefixes (Uber; conflicts with nothing in Google) | low–medium (conventions vary; individual switches) |
| `constk` | google-decisions:constant-names/mixedcaps | constants named `kFoo`/`KFoo` | low |
| `localvar` | google-practices:vardeclinitialization, uber:local-variable-declarations | single-name local `var x = expr` with no type and a non-zero value (prefer `:=`) | low |
| `testtable` | google-decisions:table-tests-identifying-the-row, google-decisions:subtest-names | range index used in `t.Run` names or failure messages while no row field is printed; `t.Run` names with `/`, whitespace or control characters | low |
| `tests` | google-decisions:examples, google-decisions:test-same-package, google-decisions:test-different-package | `func Example…` outside `_test.go`; examples in a non-`_test` package; test-only directories whose package lacks the `_test` suffix | very low |

### P3 — heuristics: prototype, measure, keep only if they pass the bar

`ptr-to-interface` fields (gocritic covers parameters), `unlock-without-defer`,
`int-duration-param` (`timeout int`, `intervalMillis int64`), `map-capacity-hint`,
`loop-const-byte-conversion`, `single-use-global-const`, `generic-single-instantiation`,
`param-name-consistency`, `undocumented-sync` / `-cleanup` / `-sentinel`,
`flag-name-style` / `flag-outside-main` (Google-specific flag conventions),
`background-in-library` (contextcheck covers part), `import-group-order` (try a
`gci` section config first: standard, default, blank — the Google proto group is
the only part gci cannot express), `literal-closing-brace`, `multiline-signature`,
`split-string-literal`, `inline-arg-comment`.

### Not planned

- **Already covered by an enabled linter**: Yoda conditions (staticcheck ST1017,
  gocritic yodaStyleExpr), `%q` (gocritic sprintfQuotedString), printf-name
  suffix (goprintffuncname; only its gap for value-returning wrappers is left),
  context as the first parameter (revive), context in structs (containedctx).
- **Contradict Google, which has priority**: Uber's `_` prefix for unexported
  globals, `/* name */` comments on bare arguments, `new(T)` → `&T{}`, two-group
  imports. They can be added later as Uber-only switches if a project follows
  Uber.
- **Judgement disguised as syntax**: assertion or validation helpers, table-test
  branching, test doubles' names, interface ownership, goroutine lifetimes,
  option-pattern choice. The reviewer handles these better than any heuristic.

## Effort

P1 is about a dozen small analyzers: each is a few dozen to two hundred lines plus
`analysistest` cases, built on the same skeleton — roughly one to two days for the
module, the multichecker, the golangci-lint plugin wiring and the first five
analyzers, then a few hours per analyzer. Every analyzer that lands removes one
or more rules from the reviewer bundles.
