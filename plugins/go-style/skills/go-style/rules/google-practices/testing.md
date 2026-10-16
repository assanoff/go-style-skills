# Google Go Style Best Practices — Testing

Test code: where failures are reported, acceptance-test APIs, transports, `t.Error` versus
`t.Fatal`, test helpers, table literals and the scope of setup.

### google-practices:test-functions — Leave testing to the Test function
- **meta:** severity=should · scope=test · check=llm · custom=validation-helper · overlaps=google-decisions:assert,google-decisions:mark-test-helpers
- **rule:** Fail tests in the `Test` function, where the logic and the failure message stay
  clear. Test helpers do setup and cleanup (their failures are environment failures);
  assertion helpers that check results and fail the test are not idiomatic. For validation
  shared by many cases: inline it (even if repetitive), use a table test with the checks in
  the loop, or write a function that returns a value or `error` (or a `cmp.Option`) instead
  of taking `*testing.T`, and let the `Test` decide whether and how to fail.
- **look for:** non-`Test` functions that take `*testing.T` and call `t.Error*`/`t.Fatal*`
  after comparing results; shared `checkX(t, got, want)` helpers whose messages cannot show
  the caller's inputs.
- **skip:** setup helpers failing on environment errors (test-helper-error-handling);
  third-party assertion libraries (google-decisions:use-package-testing).
- **example:** `checkPolygon(t, got, want)` -> `if diff := cmp.Diff(want, got, polygonCmp()); diff != "" { t.Errorf(...) }`

### google-practices:test-validation-apis-writing — Writing an acceptance test
- **meta:** severity=consider · scope=body · check=llm
- **rule:** When a library offers acceptance tests that let users validate their own
  implementations of its interfaces (like `fstest.TestFS`), put them in a package named
  after the library plus `test` (`chesstest`). The entry point takes the implementation
  under test and returns an `error` saying which invariant broke and how: fail fast with
  sentinel or custom error types, or aggregate all failures in a custom error type. It calls
  `t.Fatal` only for setup failures (keep going) and is no way around the assertion
  guidance: the user's `Test` decides how to report the error.
- **look for:** exported `ExerciseX`/`VerifyX` functions that take `*testing.T` and fail on
  invariant violations instead of returning errors; errors that do not name the broken
  invariant; acceptance helpers living outside an `xxxtest` package.
- **skip:** `t.Fatal` on provisioning failures inside such helpers.
- **example:** `func ExercisePlayer(t *testing.T, p chess.Player)` failing internally -> `func ExercisePlayer(b *chess.Board, p chess.Player) error`

### google-practices:use-real-transports — Use real transports
- **meta:** severity=consider · scope=test · check=llm · custom=fake-rpc-client
- **rule:** When testing integrations over HTTP or RPC, connect the real production client
  to a test double (fake, stub or mock) of the backend server instead of hand-implementing
  the client: imitating client behaviour correctly is hard, and the real client exercises
  more real code. Where possible use a testing library from the service's authors.
- **look for:** hand-written fakes implementing a generated `XxxClient` interface or a
  wrapper interface around it; stubbed `http.Client`/`RoundTripper` where an
  `httptest.Server` or an in-process RPC server would do.
- **skip:** code under test that does not touch the transport.
- **example:** `type fakeOpsClient struct{}` implementing `OperationsClient` -> the real `OperationsClient` dialled to a fake `OperationsServer`

### google-practices:t-fatal — t.Error vs. t.Fatal
- **meta:** severity=should · scope=test · check=llm · custom=fatal-in-table-loop · overlaps=google-decisions:keep-going
- **rule:** Tests generally keep going after a problem. `t.Fatal` fits when setup fails and
  the rest of the test cannot run (especially in setup helpers), and in a table test for
  failures in setup before the loop. When one table entry cannot continue: without
  subtests, use `t.Error` and `continue`; inside a `t.Run` subtest use `t.Fatal`, which ends
  only that subtest. `t.Fatal` is never safe from other goroutines (t-fatal-goroutine).
- **look for:** `t.Fatal*` directly in a table loop body outside `t.Run`, which abandons the
  remaining entries; `t.Error` on a row without `continue` when later checks use the broken result.
- **skip:** `t.Fatal*` inside `t.Run` closures or before the loop.
- **example:** `for _, tc := range tests { if err != nil { t.Fatalf(...) } }` -> `t.Errorf(...); continue`, or a `t.Run` subtest

### google-practices:test-helper-error-handling — Error handling in test helpers
- **meta:** severity=consider · scope=test · check=lint+llm · lint=thelper~Helper\(\) · custom=helper-returns-error · overlaps=google-decisions:mark-test-helpers
- **rule:** When a setup or cleanup helper fails, the test usually cannot continue: call
  `t.Fatal*` in the helper rather than returning the error to every caller, with a message
  saying what failed and why (`Setup failed: could not write pak0 asset: %v`). Call
  `t.Helper()` so failures point at the calling line; a helper that cannot fail needs no
  `t` parameter at all. Register teardown with `t.Cleanup`.
- **look for:** helpers taking `*testing.T` that return an `error` for the caller to check;
  `t.Fatal(err)` with no context; helpers whose only use of `t` is `t.Helper()`.
- **skip:** missing `t.Helper()`, which thelper reports; acceptance-test APIs that return
  validation errors by design (test-validation-apis-writing).
- **example:** `func addGameAssets(t *testing.T, dir string) error` -> `func mustAddGameAssets(t *testing.T, dir string)` calling `t.Fatalf("Setup failed: ...: %v", err)`

### google-practices:t-fatal-goroutine — Don't call t.Fatal from separate goroutines
- **meta:** severity=must · scope=test · check=lint+llm · lint=govet:testinggoroutine,staticcheck:SA2002
- **rule:** `t.Fatal`, `t.FailNow` and similar may only be called from the goroutine running
  the test or subtest; goroutines the test starts report with `t.Error` and return.
  `t.Parallel` does not change this. Helpers that fail fatally must run on the test's goroutine.
- **look for:** helpers that call `t.Fatal*` invoked inside goroutines, `errgroup.Go` or
  `sync.WaitGroup.Go` closures, or callbacks run on other goroutines (vet checks only
  `go` statements and the functions they start directly).
- **skip:** `t.Fatal*` written directly in a `go` statement's function — vet and
  staticcheck report it.
- **example:** `go func() { if err := e.Vroom(); err != nil { t.Fatalf(...) } }()` -> `t.Errorf(...); return`

### google-practices:t-field-names — Use field names in struct literals
- **meta:** severity=consider · scope=test · check=llm · custom=unkeyed-table-test · overlaps=google-decisions:literal-field-names,google-decisions:literal-zero-value-fields
- **rule:** In table-driven tests, prefer field names in test-case struct literals,
  especially when the table covers a lot of vertical space (more than 20-30 lines), when
  adjacent fields share a type, or to omit fields that hold the zero value.
- **look for:** long tables of positional rows; rows like `{"a", "b", "", true}` with
  adjacent same-typed fields; positional rows spelling out zero values to keep their place.
- **skip:** short tables with a few distinct-typed fields.
- **example:** `{[]string{"a", ""}, ",", true, "a"}` -> `{slice: []string{"a", ""}, separator: ",", skipEmpty: true, want: "a"}`

### google-practices:t-common-setup-scope — Keep setup code scoped to specific tests
- **meta:** severity=should · scope=test · check=llm · custom=test-init-setup
- **rule:** Scope setup of resources and dependencies as closely as possible to the test
  cases that need them: call a setup helper (`mustLoadDataset(t)`) explicitly in those tests
  instead of preparing it for the whole package in `init()` or package-level initializers,
  so running one test alone (`go test -run TestX`) does not pay for slow, failure-prone
  setup it does not use.
- **look for:** `func init()` in `_test.go` files that loads data, starts servers or
  connects to backends; package-level test variables initialised by such calls; `TestMain`
  fixtures that only some tests use.
- **skip:** cheap constant fixtures; setup every test needs and that requires teardown
  (t-custom-main) or is amortized with `sync.Once` (t-setup-amortization).
- **example:** `func init() { dataset = mustLoadDataset() }` -> `data := mustLoadDataset(t)` in each test that needs it

### google-practices:t-custom-main — When to use a custom TestMain entrypoint
- **meta:** severity=consider · scope=test · check=llm
- **rule:** Use a custom `TestMain` only when all tests in the package need common setup
  that requires teardown, typically an expensive resource in functional tests; it is not the
  first choice, so try an ordinary helper or `sync.Once` amortization first. Put setup in a
  function (`runMain(ctx, m)`) that defers its teardown and returns `m.Run()`'s code, so
  `os.Exit` in `TestMain` does not skip the defers. Keep tests hermetic: each resets any
  global state it modifies.
- **look for:** `TestMain` preparing resources only some tests use; teardown deferred in
  the function that calls `os.Exit`; tests leaving shared state (database rows, package
  variables) changed for later tests.
- **skip:** `TestMain` whose setup every test depends on and that tears it down correctly.
- **note:** Since Go 1.15 `TestMain` may simply return after `m.Run()`: the exit code is
  propagated and deferred teardown runs.

### google-practices:t-setup-amortization — Amortizing common test setup
- **meta:** severity=consider · scope=test · check=llm
- **rule:** A `sync.Once` around common setup may be appropriate (not required) when the
  setup is expensive, applies only to some tests and needs no teardown; keep its error and
  fail in each calling test. Be careful when the setup depends on a context: a second
  concurrent caller waits for the first and cannot honour its own cancellation.
- **look for:** expensive setup repeated across many tests; once-guarded setup that needs
  teardown (nowhere to register it), takes a `context.Context`, or swallows its error.
- **skip:** cheap setup; setup all tests need that requires teardown (t-custom-main).
- **note:** `sync.OnceValues` (Go 1.21) packages the once, data and error in one value.
