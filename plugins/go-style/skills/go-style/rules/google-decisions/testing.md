# Google Style Decisions — Testing

Test code: failure messages that can be diagnosed without reading the test, comparisons
and diffs, checking errors, and test structure (subtests, tables, helpers, test packages,
package `testing`).

### google-decisions:assert/libraries — Assertion libraries: no assert helpers
- **meta:** severity=must · scope=test · check=llm · custom=assertion-helper
- **rule:** Do not create assertion libraries or generic assert helpers that combine the
  check with reporting the failure (`assertEqual(t, got, want)`). They stop the test early
  or drop context the test has, give poor messages and split tests into competing DSLs.
  Use plain Go: an `if` with `cmp.Equal`, `cmp.Diff` or `==`, then `t.Errorf` in the `Test`.
- **look for:** test functions taking `*testing.T`/`testing.TB` plus got/want-like or `any`
  values that compare them and call `t.Error*`/`t.Fatal*`; in-repo `assert`/`check`/`expect`
  test packages and fluent `expect(x).To(...)` DSLs; `t.Helper()` dressing up such checks.
- **skip:** setup/cleanup helpers failing on environment errors (mark-test-helpers);
  third-party libraries such as testify or gomega (use-package-testing); `cmp.Option` factories.
- **example:** `assert.IntEq(t, "obj.Comments", obj.Comments, 2)` -> `if !cmp.Equal(got, want) { t.Errorf("BlogPost = %v, want %v", got, want) }`
- **note:** Strong Google stance: google-guide:local-consistency rejects local consistency as
  a reason to use assertion libraries. Teams standardised on assert helpers may opt out.

### google-decisions:assert/domain-helpers — Assertion libraries: comparison helpers return values
- **meta:** severity=should · scope=test · check=llm · custom=validation-helper
- **rule:** A domain-specific comparison or validation helper returns a value or an `error`
  (or offers a `cmp.Option`) that the `Test` uses in its own failure message, instead of
  taking `*testing.T` and failing inside. Non-trivial helpers deserve their own tests.
- **look for:** `checkX(t, got)`, `verifyX(t, ...)`, `validateX(t, ...)` helpers that call
  `t.Errorf`/`t.Fatalf` on a mismatch, especially when shared by many tests whose inputs
  the helper's message cannot show.
- **skip:** setup/cleanup helpers whose failures are environment failures
  (mark-test-helpers); generic assert-style helpers (assert/libraries).
- **example:** `func checkLen(t *testing.T, p Post) {...}` -> `func postLength(p Post) int { return len(p.Body) }`, compared in the test

### google-decisions:identify-the-function — Identify the function
- **meta:** severity=should · scope=test · check=llm · custom=failure-msg-func-name
- **rule:** In most tests the failure message names the function that failed, even if the
  test name makes it look obvious: `YourFunc(%v) = %v, want %v`, not just
  `got %v, want %v`, so a failure can be diagnosed without reading the test source.
- **look for:** `t.Errorf`/`t.Fatalf` formats that start with `got`, `want`, `expected`,
  `unexpected` or `mismatch`, or name no function at all; tests calling several functions
  where the message does not say which one failed.
- **skip:** setup failures such as `t.Fatalf("Setup: ...: %v", err)` (level-of-detail);
  messages that name the operation in words (`Decode returned ...`).
- **example:** `t.Errorf("got %v, want %v", got, want)` -> `t.Errorf("Add(%d, %d) = %d, want %d", a, b, got, want)`

### google-decisions:identify-the-input — Identify the input
- **meta:** severity=should · scope=test · check=llm
- **rule:** In most tests failure messages include the function's inputs when they are
  short. If the relevant inputs are large or opaque, give the test case a description of
  what is being tested and print that description in the message.
- **look for:** messages like `Parse() = %v, want %v` that leave out the arguments; large or
  opaque inputs with no description printed in the message.
- **skip:** table rows identified only by subtest name or index
  (table-tests-identifying-the-row); a message that also lacks the function name gets one
  combined finding under identify-the-function.
- **example:** `t.Errorf("Split() = %q, want %q", got, tc.want)` -> `t.Errorf("Split(%q, %q) = %q, want %q", tc.s, tc.sep, got, tc.want)`

### google-decisions:got-before-want — Got before want
- **meta:** severity=should · scope=test · check=llm · custom=want-before-got
- **rule:** Print the actual value before the expected one, in the standard form
  `YourFunc(%v) = %v, want %v`, and write "got"/"want" rather than "actual"/"expected".
  Diffs have no obvious direction, so their messages should state the key (print-diffs).
- **look for:** formats with the expected value first, like `"want %v, got %v"` or
  `"expected %v but got %v"`; `= %v, want %v` fed with `want, got`; "expected"/"actual" wording.
- **skip:** diff keys such as `(-want +got)` (print-diffs); suffixes like
  `want error presence = %v` that follow the got value.
- **example:** `t.Errorf("expected %d, got %d", want, got)` -> `t.Errorf("Sum(%v) = %d, want %d", in, got, want)`

### google-decisions:compare-full-structures — Full structure comparisons
- **meta:** severity=should · scope=test · check=llm · custom=field-by-field-compare
- **rule:** For returned structs, slices, arrays and maps, don't hand-code field-by-field
  comparisons: build the expected value and compare it whole with a deep comparison
  (`cmp.Equal`/`cmp.Diff`), using `cmpopts` (e.g. `IgnoreInterfaces`) for approximate or
  uncomparable fields. Exception: irrelevant fields that would obscure the test's intent.
  Multiple return values need no wrapper struct; compare and print each one.
- **look for:** runs of `if got.A != want.A {...}`, one per field; hand-written loops comparing
  slice elements or map entries; a few fields of a returned struct checked for no reason.
- **skip:** multiple return values compared one by one; partial checks where the other
  fields are noise for the test.
- **example:** `if got.Name != "a" {...}; if got.Age != 3 {...}` -> `want := User{Name: "a", Age: 3}; if diff := cmp.Diff(want, got); diff != "" {...}`

### google-decisions:compare-stable-results — Compare stable results
- **meta:** severity=should · scope=test · check=llm · custom=serialized-output-compare
- **rule:** Don't compare output whose exact form depends on a package you don't own:
  formatted strings and serialized bytes are generally unstable (`json.Marshal` output has
  changed before). Compare stable, semantically relevant data instead, e.g. parse the JSON
  and compare it with the expected structure.
- **look for:** `==`, `bytes.Equal` or `cmp.Diff` of `json.Marshal`, `protojson` or
  `prototext` output, or of `fmt` renderings of other packages' types, against literal strings.
- **skip:** exact output of the package under test's own formatter when those bytes are its
  contract (not bytes produced via `encoding/json`, protobuf or `fmt`).
- **example:** `if string(b) != wantJSON {...}` -> `json.Unmarshal(b, &got)`, then `cmp.Diff(want, got)`

### google-decisions:keep-going/error-over-fatal — Keep going: t.Error for mismatches
- **meta:** severity=should · scope=test · check=llm
- **rule:** Tests keep going after a failure so one run reports every broken check. Report
  mismatches with `t.Error*`, one per compared property. Use `t.Fatal*` only when going on
  would be meaningless or misleading: an unexpected error, or a wrong result that the next
  step consumes (bad `Encode` output before `Decode`).
- **look for:** `t.Fatalf` on a plain value mismatch followed by more independent checks;
  several properties of one result checked with consecutive `t.Fatal*` calls.
- **skip:** `t.Fatal*` on unexpected errors, failed setup, the last check, or a value later
  steps depend on; `t.Fatal` ending a table row inside its `t.Run` subtest.
- **example:** `if gotMean != wantMean { t.Fatalf(...) }` followed by more checks -> `t.Errorf(...)`

### google-decisions:keep-going/table-subtests — Keep going: subtests in table tests
- **meta:** severity=consider · scope=test · check=llm
- **rule:** In table-driven tests, consider running each row as a `t.Run` subtest and ending
  a broken row with `t.Fatal`, rather than `t.Error` followed by `continue` (GoTip #25).
- **look for:** table loops without `t.Run` that use `t.Errorf(...); continue` to abandon a row.
- **skip:** small tables where `continue` stays simple (the guide's `TestDivide` uses it).
- **example:** `t.Errorf(...); continue` -> `t.Run(tc.name, func(t *testing.T) { ...; t.Fatalf(...) })`

### google-decisions:types-of-equality/cmp — Equality comparison and diffs: use cmp
- **meta:** severity=should · scope=test · check=llm
- **rule:** `==` handles scalars and comparable values but compares pointers by identity and
  cannot compare slices; for complex values use `cmp.Equal`, and `cmp.Diff` for a readable
  diff. Protocol buffer messages need `protocmp.Transform()`. Prefer `cmp` in new code over
  older libraries such as `pretty` (equates values that print alike, compares unexported
  fields, unfit for protos); old code may keep them for consistency or migrate when practical.
- **look for:** `got != want` between pointers to freshly built structs; `cmp` on proto
  messages without `protocmp.Transform()`; `pretty` adopted in new tests.
- **skip:** `reflect.DeepEqual` (types-of-equality/deepequal); scalar `==`; files that
  consistently use `pretty`.
- **example:** `if got != want` (both `*Doc`) -> `if !cmp.Equal(got, want) { t.Errorf("AddPost() = %+v, want %+v", got, want) }`

### google-decisions:types-of-equality/deepequal — Equality comparison and diffs: no reflect.DeepEqual
- **meta:** severity=should · scope=test · check=lint · lint=forbidigo~DeepEqual
- **rule:** Don't use `reflect.DeepEqual` to check equality: it is sensitive to unexported
  fields and other implementation details. Move existing uses to `cmp`.
- **skip:** all of it; forbidigo reports every use in test files.
- **example:** `if !reflect.DeepEqual(got, want)` -> `if diff := cmp.Diff(want, got); diff != ""`

### google-decisions:types-of-equality/production — Equality comparison and diffs: cmp stays in tests
- **meta:** severity=should · scope=body · check=lint+llm · lint=depguard~import '[^']*go-cmp
- **rule:** `cmp` is designed for tests, not production: it may panic when it suspects a
  comparison is done wrong, and a spurious panic in production can be fatal. Don't call
  `cmp.Equal`/`cmp.Diff` from production code.
- **look for:** `cmp` reached from production code through shared helper packages that the
  depguard file globs exempt.
- **skip:** test-only helper packages (`footest`, `testutil`) imported only by tests.

### google-decisions:level-of-detail — Level of detail
- **meta:** severity=consider · scope=test · check=llm
- **rule:** `YourFunc(%v) = %v, want %v` fits most tests; adjust when needed. For complex
  interactions say which call failed and include relevant system state (or log it); for
  boilerplate-heavy structs print the important parts without hiding the data; setup failures
  need little detail (`t.Fatalf("Setup: Failed to set up test database: %s", err)`). Use `%q`
  for strings, `%+v` for small structs, a diff for large values; trigger the failure once to check.
- **look for:** repeated calls to one function where the message does not say which one
  failed; strings printed with `%v`/`%s` where empty or blank values vanish; huge values
  dumped with `%v`; setup failures padded with dumps of test inputs.
- **skip:** the conventional format when it is enough.

### google-decisions:print-diffs — Print diffs
- **meta:** severity=should · scope=test · check=llm · custom=cmp-diff-legend
- **rule:** For large outputs print a diff instead of both values (`cmp.Diff` preferred in
  new code; `pretty.Compare`, or `diff` for multi-line strings, also work). State the
  direction to match the argument order: `(-want +got)` for `cmp.Diff(want, got)`,
  `(-got +want)` for `(got, want)`, `(want -> got)` for `messagediff`. Print a newline before
  the diff. The argument order itself is a non-decision: be locally consistent.
- **look for:** two large values printed with `%v`/`%+v`; diff messages with no direction
  key; a key contradicting the `cmp.Diff` argument order; a diff `%s` not preceded by `\n`.
- **skip:** small values where `= %v, want %v` is clearer; the chosen argument order as such.
- **example:** `t.Errorf("Foo() mismatch: %s", cmp.Diff(got, want))` -> `t.Errorf("Foo() mismatch (-want +got):\n%s", cmp.Diff(want, got))`

### google-decisions:test-error-semantics/strings — Test error semantics: no message matching
- **meta:** severity=should · scope=test · check=llm · custom=error-string-compare
- **rule:** Don't compare error strings (or use a plain `cmp` on errors) to check which error
  came back: rewording a message breaks the test, making it a change detector. Test semantic
  information: if only failure matters, check `err != nil`; to match a specific error use
  `errors.Is` or `cmp` with `cmpopts.EquateErrors`. Allowed: string checks that messages from
  the package under test have a property (e.g. name the parameter). If a dependency's errors
  carry too little semantics, file a bug rather than parse its messages.
- **look for:** `err.Error() == "..."` or `strings.Contains(err.Error(), ...)` used to tell
  errors apart; `cmp.Diff(tc.wantErr, err)` without `EquateErrors`; `EqualError`-style checks.
- **skip:** property checks on the package under test's own messages.
- **example:** `if err.Error() != "not found"` -> `if !errors.Is(err, ErrNotFound)`

### google-decisions:test-error-semantics/bool-want — Test error semantics: bool wantErr
- **meta:** severity=consider · scope=test · check=llm · custom=wanterr-anyerror-only
- **rule:** If errors are compared with `cmp` and `cmpopts.EquateErrors` but every `wantErr`
  is `nil` or `cmpopts.AnyError`, `cmp` is unnecessary mechanism: make the field a `bool`
  and compare error presence with `!=`.
- **look for:** table fields `wantErr error` that only ever hold `nil` or `cmpopts.AnyError`.
- **example:** `wantErr: cmpopts.AnyError` -> `wantErr: true` with `if gotErr := err != nil; gotErr != tc.wantErr {...}`

### google-decisions:subtests — Subtests
- **meta:** severity=should · scope=test · check=llm
- **rule:** Subtests (`t.Run`) help with setup and cleanup, parallelism and filtering, notably
  in table tests, but are not mandatory. A subtest should not depend on other cases having
  run, for its success or its initial state: each must work alone under `go test -run` or
  a test filter.
- **look for:** state created or changed in one `t.Run` and read by a later one (shared
  variables, fakes or databases filled by an earlier case); step-like cases (`create`,
  `update`, `delete`) on one shared fixture.
- **skip:** tests without subtests; read-only fixtures built before the loop.

### google-decisions:subtest-names — Subtest names
- **meta:** severity=should · scope=test · check=llm · custom=subtest-name-chars
- **rule:** Name subtests like function identifiers, not prose: readable in output after
  escaping and easy to type in `-run` or test filters. Avoid spaces (turned into `_`),
  non-printing characters and especially `/` (a level separator in filters). Put a longer
  description in a separate field, printed with `t.Log` or in the failure message, and
  print the inputs in the message, where the runner does not escape them.
- **look for:** `t.Run` names (literals or the table's `name` field) with `/`, spaces,
  non-printing characters or whole sentences; names built from raw inputs such as paths,
  URLs or time zones.
- **skip:** short identifier-like names using `_`, `-`, `=`; long text kept in a `desc` field.
- **example:** `t.Run("AM/PM confusion", ...)` -> `t.Run("am_pm_confusion", ...)`

### google-decisions:table-driven-tests — Table-driven tests
- **meta:** severity=should · scope=test · check=llm
- **rule:** Use table-driven tests when many cases share the same checking logic (output
  equals expected, or outputs meet the same invariants), with useful failure messages
  (function and inputs; no row numbers). Cases needing different logic go to separate test
  functions (e.g. one table for valid outputs, one for errors) or a sequence of subtests. A
  simple error-presence case with no conditional flow may share the table; watch it grow.
- **look for:** copy-pasted blocks or test functions calling one function with different
  inputs; loop bodies branching on row fields to choose which checks run (beyond a simple
  `wantErr` presence check); success and error rows with diverging checks in one loop.
- **skip:** row fields that select setup or dependencies (table-tests-data-driven);
  positional row literals, which the guide's own example uses.
- **note:** Field names in row literals are covered by google-practices:t-field-names.

### google-decisions:table-tests-data-driven — Data-driven test cases
- **meta:** severity=should · scope=test · check=llm · custom=table-row-mode-switch
- **rule:** Don't let row values dictate conditional behavior inside the test case, such as
  a field that picks a fake or real dependency plus a `switch` in the loop to build it.
  Duplicate instead: separate test functions with their own setup, sharing the case type.
  The clarity of that duplication is needed for readability (TotT: Data Driven Traps).
- **look for:** enum or bool row fields (`codex`, `mode`, `useFake`) driving `switch`/`if` in
  the loop to set up different dependencies; `default: t.Fatalf("unknown ...")` on row fields.
- **skip:** simple `wantErr`-style presence checks (table-driven-tests).
- **example:** `switch test.codex { case fake: ...; case prod: ... }` -> `TestDecode` and `TestDecodeWithFake` sharing `decodeCase`

### google-decisions:table-tests-identifying-the-row — Identifying the row
- **meta:** severity=must · scope=test · check=llm · custom=table-row-index
- **rule:** Do not use the row's index in the table instead of naming the case or printing
  its inputs. Give rows a name or description and print it with failures; with subtests the
  name must identify the row and follow subtest-names. Even with `t.Run`, failure messages
  must identify the input.
- **look for:** `t.Errorf("case %d failed", i)`; `t.Run(strconv.Itoa(i), ...)` or
  `t.Run("", ...)` (auto-named `#00`); messages in table loops showing neither inputs nor a
  row description and relying on the subtest name alone.
- **skip:** an index printed in addition to the inputs or the name.
- **example:** `t.Errorf("Failed on case #%d", i)` -> `t.Errorf("ToUpper(%q) = %q, want %q", tc.input, got, tc.want)`

### google-decisions:mark-test-helpers — Test helpers
- **meta:** severity=should · scope=test · check=lint+llm · lint=thelper~(Helper\(\)|should be the first)
- **rule:** Test helpers do setup or cleanup, so their failures are environment failures, not
  failures of the code under test. A helper taking `*testing.T` calls `t.Helper()` so
  failures point at the caller; `t` goes after a `context.Context`, if any, and before other
  parameters. Same for `*testing.B`, `*testing.F` and `testing.TB` helpers. Don't use
  `t.Helper()` to build assertion helpers that hide what caused a failure (see assert).
- **look for:** fixture methods that keep a `*testing.T` field and fail through it without
  calling `Helper()` (thelper checks only parameters); validators dressed up as helpers.
- **skip:** missing `t.Helper()` and parameter order, which thelper reports (its parameter
  name check is outside this rule); `Test*` functions and `t.Run` closures.
- **example:** `func readFile(name string, t *testing.T) string` -> `func readFile(t *testing.T, name string) string { t.Helper(); ... }`

### google-decisions:test-same-package — Tests in the same package
- **meta:** severity=consider · scope=test · check=llm · custom=example-in-internal-test
- **rule:** Tests may live in the package under test (`foo_test.go` with `package foo`,
  without importing `foo`), which gives access to unexported identifiers for better coverage
  and more concise tests. Runnable examples declared there lack the package name users need
  in their code; examples belong in the `_test` package.
- **look for:** `func Example...` in test files declared `package foo`, whose code reads
  `New()` instead of `foo.New()`.
- **skip:** ordinary same-package tests, which are explicitly allowed.

### google-decisions:test-different-package — Tests in a different package
- **meta:** severity=should · scope=test · check=llm · custom=test-only-pkg-suffix
- **rule:** When a test can't or shouldn't live in the package under test, such as an
  integration test with no obvious owning library, or a same-package test that would create
  an import cycle (it needs a test utility that imports the package), use a package name
  with the `_test` suffix (`gmailintegration_test`, `fireworks_test`). This is the allowed
  exception to "no underscores" in package names.
- **look for:** directories holding only `_test.go` files whose package lacks the `_test`
  suffix (`package integration`); test utilities duplicated, or tests moved to unrelated
  packages, to dodge a cycle that an external `foo_test` package would solve.
- **skip:** same-package tests (test-same-package).

### google-decisions:use-package-testing — Use package `testing`
- **meta:** severity=must · scope=test · check=lint+llm · lint=depguard~import '[^']*(testify|gomega|ginkgo|check\.v1|goconvey|quicktest|matryer/is|gotest\.tools)
- **rule:** The standard `testing` package is the only permitted test framework: third-party
  assertion libraries and testing frameworks are not allowed. `testing` already provides
  top-level tests, benchmarks, runnable examples, subtests, logging and (fatal) failures,
  and works with composite literals and if-with-initializer to keep tests clear.
- **look for:** framework imports missing from the depguard list (other matcher, BDD or
  suite libraries); in-house frameworks that replace `testing` (suite runners with
  setup/teardown hooks).
- **skip:** `go-cmp` and `protocmp`, comparison libraries the guide recommends; home-grown
  assert helpers (assert/libraries).
- **note:** This is a mandate for Google's codebase. Teams standardised on testify or gomega
  may opt out of this rule and the depguard list; the failure-message rules still apply.
