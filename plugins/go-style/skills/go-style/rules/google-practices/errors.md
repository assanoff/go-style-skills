# Google Go Style Best Practices — Error handling

How to structure, annotate, wrap and log errors, and when to stop the program or panic.

### google-practices:error-handling — Handle errors deliberately
- **meta:** severity=should · scope=body · check=lint+llm · lint=errcheck, nilerr · overlaps=google-decisions:handle-errors
- **rule:** Produce and consume errors deliberately: don't ignore an error or blindly pass it up;
  consider whether the current function is best placed to handle it, give new errors structure
  when callers need it, and add information the caller or callee lacks. A reasonable exception to
  not ignoring errors is orchestrating related operations where only the first error matters —
  `errgroup` provides that abstraction.
- **look for:** errors discarded with `_` and no reason; hand-rolled `sync.WaitGroup` plus mutex
  code that keeps the first error of a group of operations (an `errgroup.Group` fits).
- **skip:** unchecked error results and `return nil` inside `if err != nil` — errcheck and nilerr
  report them.

### google-practices:error-structure — Give errors a structure callers can check
- **meta:** severity=should · scope=body · check=llm
- **rule:** If callers (tests included) need to tell error conditions apart, make that
  programmatic: sentinel values (compared with `==`, or `errors.Is` when the function may wrap
  them) or error types whose fields carry the extra data (`os.PathError`'s path). Status codes are
  optional; if used, use canonical codes. Callers should never need to parse messages.
- **look for:** conditions callers branch on returned as ad-hoc `errors.New`/`fmt.Errorf` values;
  data the caller needs (path, code, ID) present only in the message; `==` against the sentinels
  of a function that wraps its errors.
- **skip:** `==` against sentinels the callee returns unwrapped — the guide calls this adequate;
  errors no caller needs to distinguish.
- **example:** `return errors.New("duplicate")` (callers match it) -> `return ErrDuplicate` with `var ErrDuplicate = errors.New("duplicate")`

### google-practices:error-structure/string-matching — Don't distinguish errors by their text
- **meta:** severity=should · scope=body · check=llm · custom=error-string-match
- **rule:** Do not distinguish errors by their string form; use sentinels, error types,
  `errors.Is`/`errors.As` or status codes instead.
- **look for:** `err.Error()` passed to `strings.Contains`/`HasPrefix`/`regexp.MatchString`,
  compared with `==`, or used as a `switch` tag; the same with `fmt.Sprint(err)`.
- **skip:** test code — google-decisions:test-error-semantics allows checking message properties
  there.
- **example:** `if strings.Contains(err.Error(), "duplicate")` -> `if errors.Is(err, ErrDuplicate)`

### google-practices:error-extra-info — Add only new information to errors
- **meta:** severity=should · scope=body · check=llm · custom=noise-error-annotation
- **rule:** When annotating an error, add context the current function has and the error lacks
  (what it was trying to do) without repeating what the underlying error already says (`os`
  errors already include the path). Don't add an annotation that only says something failed —
  return the error as is.
- **look for:** wrappers restating the callee's details (`fmt.Errorf("could not open %s: %v",
  name, err)` around an `os.Open` error); empty annotations (`"failed: %v"`, `"error: %w"`).
- **skip:** annotations adding the operation or inputs the callee does not know.
- **example:** `return fmt.Errorf("failed: %v", err)` -> `return err`

### google-practices:error-extra-info/wrap-verb — Choose %v or %w deliberately
- **meta:** severity=consider · scope=body · check=llm
- **rule:** `%w` is a deliberate choice, not mandatory. Use `%v` (drops the error's structure)
  for plain annotation, for errors meant for logs or display, and to create fresh errors at system
  boundaries (RPC, IPC, storage), where domain errors are better translated into a canonical space
  such as gRPC status codes. Use `%w` when callers should inspect the cause with
  `errors.Is`/`errors.As` — the main case inside an application's helpers — or when the API
  documents and tests the wrapped errors as part of its contract.
- **look for:** RPC/HTTP handlers or storage layers returning `%w`-wrapped internal errors to
  clients; `%v` where a caller runs `errors.Is`/`errors.As` on the result or the doc promises a
  wrapped sentinel; `errors.Unwrap(err) == X` checks (they miss multi-errors).
- **skip:** `%v` that merely could have been `%w` — the guide treats `%v` as the general-purpose verb.

### google-practices:error-percent-w — Put %w at the end
- **meta:** severity=consider · scope=body · check=llm · custom=errorf-wrap-at-end
- **rule:** When wrapping with `%w`, prefer the form `"...: %w"`, so the printed text runs from
  newest to oldest like the error chain; `%w` at the start prints the chain oldest-first, and `%w`
  in the middle scrambles it. Exception: sentinel errors (next rule).
- **look for:** `fmt.Errorf("%w: ...", err)` or `fmt.Errorf("... %w ...", err)` where `err` is a
  propagated error rather than a sentinel.
- **skip:** `%w` first when it wraps a sentinel; formats without `%w`.
- **example:** `fmt.Errorf("%w: read config", err)` -> `fmt.Errorf("read config: %w", err)`

### google-practices:error-percent-w-sentinel-placement — Put a wrapped sentinel first
- **meta:** severity=consider · scope=body · check=llm · custom=errorf-sentinel-first
- **rule:** When wrapping a sentinel error — one that categorizes the failure, such as
  `os.ErrInvalid` or a package-level `ErrParse` — place its `%w` at the beginning
  (`"%w: details"`) so the category is read first instead of being buried in the details.
- **look for:** sentinels wrapped last: `fmt.Errorf("...: %v: %w", err, ErrX)`,
  `fmt.Errorf("lookup %q: %w", key, ErrNotFound)`.
- **note:** the guide's examples format the underlying cause with `%v` after the sentinel; Go 1.20+
  also allows a second `%w` (`"%w: ...: %w"`), which the guide does not discuss.
- **example:** `fmt.Errorf("bad header: %v: %w", err, ErrParse)` -> `fmt.Errorf("%w: bad header: %v", ErrParse, err)`

### google-practices:error-logging — Log errors usefully and sparingly
- **meta:** severity=consider · scope=body · check=llm
- **rule:** When a function reports an error by logging instead of returning it, the message
  should say clearly what went wrong and include what a maintainer needs to diagnose it. Be careful
  with PII: many log sinks are unfit for sensitive user data. Use ERROR level sparingly — it
  flushes and costs more, and should mean "actionable", not "more serious than a warning" — and
  prefer monitoring and alerting over log lines someone has to notice.
- **look for:** vague messages (`log.Error("failed")`) without the operation or inputs; emails,
  names, tokens or request bodies in log calls; ERROR-level logs for expected or non-actionable
  conditions, or inside hot loops.

### google-practices:error-logging/duplication — Don't log an error you also return
- **meta:** severity=should · scope=body · check=llm · custom=log-and-return
- **rule:** If you return an error, usually don't log it too: let the caller decide whether to
  log it (perhaps rate-limited with `rate.Sometimes`), recover, or stop the program. This avoids
  logspam; the cost is that the log line carries the caller's location.
- **look for:** a log call with `err` followed by `return err` or a wrapped `err` in the same
  branch; the same error logged at several layers on its way up.
- **skip:** logging that is the handling (the error is not returned); a boundary that logs details
  and returns a different, sanitized error.
- **example:** `log.Errorf("load: %v", err); return err` -> `return fmt.Errorf("load: %w", err)`

### google-practices:vlog — Verbose logging without hidden cost
- **meta:** severity=should · scope=body · check=llm · custom=vlog-eager-args
- **rule:** Use verbose logging (`log.V`) for development and tracing, ideally with a level
  convention (e.g. `V(1)` a little extra, `V(2)` tracing, `V(3)` dumps of internal state). Don't
  run expensive arguments when the level is off: `log.V(2).Infof("%v", x.Explain())` always calls
  `Explain`; when in doubt, guard with `if log.V(2) { ... }`.
- **look for:** `log.V(n).Info*` calls whose arguments call costly functions or methods
  (serializers, `Explain`/`String` on large values, dumps).
- **skip:** cheap arguments (variables, fields, `len`).
- **note:** written for glog's `log.V`; with other leveled loggers the analogous guard is
  `slog.Logger.Enabled` or zap's `Check`.
- **example:** `log.V(2).Infof("Handling %v", sql.Explain())` -> `if log.V(2) { log.Infof("Handling %v", sql.Explain()) }`

### google-practices:program-init — Report initialization errors from main
- **meta:** severity=should · scope=body · check=llm · overlaps=google-decisions:dont-panic
- **rule:** Propagate program-initialization errors (bad flags, invalid configuration) up to
  `main`, which calls `log.Exit` with a message that explains how to fix the problem. Don't use
  `log.Fatal` for these: a stack trace pointing at the check helps less than an actionable message.
- **look for:** flag or config validation helpers that call `log.Fatal`, `os.Exit` or `panic`
  instead of returning an error; startup failures reported with a stack trace, or without naming
  the bad flag or setting and what is expected.
- **skip:** `init` and Must functions, where a panic is acceptable (when-to-panic).
- **note:** `log.Exit`/`log.Fatal` are glog's (Fatal prints a stack trace, Exit does not); with
  the standard `log`, the equivalent is returning to `main` and exiting there via `log.Fatal` or
  `os.Exit(1)` with an actionable message.

### google-practices:checks-and-panics — Return errors; log.Fatal only for broken invariants
- **meta:** severity=should · scope=body · check=llm · overlaps=google-decisions:dont-panic · conflicts=uber:exit-in-main
- **rule:** Error handling is built on error returns: libraries should return errors rather than
  abort the program, especially for transient failures. Terminate on a failed invariant check only
  when internal state is unrecoverable, and then use `log.Fatal`, not `panic`: deferred functions
  run during a panic can deadlock or further corrupt internal or external state.
- **look for:** library code that panics or exits on I/O, network or input errors; `panic` used
  for an unrecoverable-invariant check where the guide prefers `log.Fatal`.
- **skip:** `init`, Must functions and the other cases in when-to-panic.
- **note:** `log.Fatal` is glog's in the guide. revive:deep-exit is deliberately not mapped: it
  flags the `log.Fatal` invariant checks this section endorses.

### google-practices:checks-and-panics/recover — Don't recover panics to keep running
- **meta:** severity=should · scope=body · check=llm · custom=recover-no-repanic · conflicts=effective:recover
- **rule:** Resist recovering panics to avoid crashes: the further from the panic, the less is
  known about the program's state (held locks, half-updated data), and continuing can cause harder
  failures. Surface unexpected panics with monitoring and fix the bugs. `net/http`'s recovery of
  handler panics is regarded as a historical mistake — don't copy it into servers.
- **look for:** recovery middleware or per-request/per-goroutine `defer func() { recover() ... }()`
  that logs and carries on; recovers that swallow every panic value.
- **skip:** a package recovering only its own internal panic type and re-panicking others
  (when-to-panic).

### google-practices:when-to-panic — When a panic is acceptable
- **meta:** severity=should · scope=body · check=llm
- **rule:** Panics fit API misuse that review and tests should catch (as `reflect` does),
  `panic("unreachable")` after calls that never return such as `log.Fatal`, and dying in `init` or
  Must functions (log functions must not run before flags are parsed). As an internal technique
  (e.g. deeply nested parsers) a panic needs a matching `recover` and must never escape the package
  boundary: a top-level deferred recover turns it into an error, re-panics values the code did not
  raise, and resources held on those paths must still be released (close, unlock).
- **look for:** exported functions whose internal panics can reach callers; deferred recovers
  turning any panic value into an error; locks or files held across panicking code without a
  deferred release; panics for ordinary runtime errors in library code.
- **skip:** Must helpers and `init`; standard-library-style panics on clear programmer misuse.
