# Uber Go Style Guide — Errors

How Uber declares, wraps, names and handles errors, plus type-assertion failures and panics.

### uber:error-types/matching — Error Types: support matching
- **meta:** severity=should · scope=body · check=lint+llm · lint=errorlint~comparing with, errorlint~(type assertion|type switch) · custom=error-string-match · overlaps=google-practices:error-structure
- **rule:** Decide whether callers need to match the error. If they do, support `errors.Is` and
  `errors.As`: a top-level `var ErrX = errors.New(...)` for a static message, a custom error
  type for a dynamic one. Exported error variables and types become part of the package's
  public API, so export them only when callers need to match.
- **look for:** callers matching on messages (`strings.Contains(err.Error(), "not found")`),
  a sign the producer should expose a sentinel or type; failure modes callers must tell apart
  returned as ad-hoc `errors.New`/`fmt.Errorf` values; exported error values or types nobody
  matches.
- **skip:** `==` comparisons and type assertions or switches on errors — errorlint reports them.
- **example:** `return errors.New("could not open")` -> `return ErrCouldNotOpen`, matched with `errors.Is(err, foo.ErrCouldNotOpen)`

### uber:error-types/constructor — Error Types: errors.New or fmt.Errorf
- **meta:** severity=consider · scope=body · check=lint+llm · lint=perfsprint~errors\.New, staticcheck:S1028 · conflicts=google-decisions:non-decisions
- **rule:** For errors callers don't match, use `errors.New` when the message is static and
  `fmt.Errorf` when it carries dynamic context.
- **look for:** `errors.New` built by string concatenation (`errors.New("bad id " + id)`).
- **skip:** `fmt.Errorf` with a constant message and `errors.New(fmt.Sprintf(...))` — perfsprint
  and staticcheck report them.
- **example:** `errors.New(fmt.Sprintf("file %q not found", file))` -> `fmt.Errorf("file %q not found", file)`
- **note:** Google's style decisions leave `errors.New` vs `fmt.Errorf` on constant strings to
  the author.

### uber:error-wrapping/verb — Error Wrapping: %w or %v
- **meta:** severity=should · scope=body · check=lint+llm · lint=errorlint~non-wrapping format verb · conflicts=google-practices:error-extra-info
- **rule:** When adding context with `fmt.Errorf`, choose the verb by whether callers should be
  able to match and extract the cause. `%w`, a good default for most wrapped errors, lets them
  use `errors.Is`/`errors.As` and they may come to rely on it, so when the wrapped error is a
  known variable or type, document and test it as part of the function's contract. `%v`
  deliberately hides the cause; switching to `%w` later stays possible.
- **look for:** `%w` exposing a dependency's sentinel or type that is neither documented nor
  tested; `fmt.Errorf("...: %s", err.Error())`, which drops the chain without a deliberate
  choice.
- **skip:** `%v` chosen on purpose to hide internals (errorlint flags every `%v`/`%s` applied
  to an error, intended or not).
- **note:** Google's best practices treat `%v` as the plain-annotation default and `%w` as a
  deliberate opt-in; in multi-guide runs Google's guidance wins.

### uber:error-wrapping/context — Error Wrapping: succinct context
- **meta:** severity=should · scope=body · check=llm · custom=errorf-failed-prefix · overlaps=google-practices:error-extra-info
- **rule:** Return the error as is when there is no context to add. Otherwise add context ("call
  service foo: connection refused") and keep it succinct: avoid phrases like "failed to" that
  state the obvious and pile up as the error moves up the stack ("failed to x: failed to y:
  ..."). Once an error is sent to another system, such as logs, make it clear it is an error
  (an `err` tag, a "Failed" prefix).
- **look for:** wrap messages starting with "failed to", "error" or "unable to"; wraps that add
  nothing (`fmt.Errorf("%w", err)`, `"error: %w"`).
- **skip:** log lines and other messages leaving the process; root errors with no wrapped cause;
  a package that consistently wraps with "failed to …" — report the convention once as a
  package-level note, not every instance (local consistency, google-guide:local-consistency).
- **example:** `fmt.Errorf("failed to create new store: %w", err)` -> `fmt.Errorf("new store: %w", err)`

### uber:error-naming — Error Naming
- **meta:** severity=should · scope=decl · check=lint · lint=errname
- **rule:** Prefix error values stored in global variables with `Err` (exported) or `err`
  (unexported) — this supersedes the `_` prefix for unexported globals — and suffix custom
  error types with `Error` (`NotFoundError`, `resolveError`).
- **example:** `var _errNotFound = errors.New("not found")` -> `var errNotFound = errors.New("not found")`

### uber:handle-errors-once — Handle Errors Once
- **meta:** severity=should · scope=body · check=llm · custom=log-and-return · overlaps=google-practices:error-logging
- **rule:** Handle each error only once, in whichever way fits: match it with
  `errors.Is`/`errors.As` and branch, log it and degrade gracefully when it is recoverable,
  return a well-defined domain error, or return it wrapped or verbatim. Don't, for example, log
  an error and then return it: callers up the stack will handle it too, filling logs with noise.
- **look for:** an `if err != nil` block that logs `err` and then returns it or a wrap of it;
  the same failure logged at several layers.
- **skip:** logging and continuing when the operation is optional (emitting metrics); matching
  a known error to recover while wrapping and returning all others.
- **example:** `log.Printf("could not get user %q: %v", id, err); return err` -> `return fmt.Errorf("get user %q: %w", id, err)`

### uber:handle-type-assertion-failures — Handle Type Assertion Failures
- **meta:** severity=must · scope=body · check=lint · lint=forcetypeassert · overlaps=effective:interface_conversions
- **rule:** The single-value form of a type assertion panics on the wrong type, so always use the
  "comma ok" idiom and handle the failure gracefully.
- **skip:** type switches.
- **example:** `t := i.(string)` -> `t, ok := i.(string); if !ok { /* handle */ }`

### uber:dont-panic/production — Don't Panic: production code
- **meta:** severity=must · scope=body · check=llm · custom=panic-outside-init · overlaps=google-decisions:dont-panic, effective:panic · conflicts=google-practices:when-to-panic, effective:recover
- **rule:** Production code must avoid panics, a major source of cascading failures: when an
  error occurs, return it and let the caller decide. Panic only when something irrecoverable
  happens, such as a nil dereference. Program initialization is the exception: failures that
  should abort startup may panic (`template.Must` in a package-level var). Panic/recover is not
  an error-handling strategy.
- **look for:** `panic` on invalid input, missing configuration or I/O failures in library or
  request code; `Must*` helpers applied to runtime data; `recover` used to turn panics into
  ordinary errors; a `run(args)` that panics where it could return an error.
- **skip:** package-level `Must` initializers on constant inputs; test code (tests rule).
- **example:** `if len(args) == 0 { panic("an argument is required") }` -> `return errors.New("an argument is required")`

### uber:dont-panic/tests — Don't Panic: tests
- **meta:** severity=should · scope=test · check=llm · custom=panic-in-test
- **rule:** Even in tests, prefer `t.Fatal` or `t.FailNow` over panics so the test is marked as
  failed.
- **look for:** `panic(...)` on setup failures (temp files, fixtures, decoding) in tests and
  helpers that have a `*testing.T` or `testing.TB` at hand.
- **skip:** code with no `testing.TB` (`TestMain`, package-level fixtures); goroutines started
  by the test, where `t.Fatal` must not be called.
- **example:** `panic("failed to set up test")` -> `t.Fatal("failed to set up test")`
