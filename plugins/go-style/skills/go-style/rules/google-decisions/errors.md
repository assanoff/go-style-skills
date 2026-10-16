# Google Style Decisions — Errors

Errors: how functions return them, how error strings read, handling every error
deliberately, avoiding in-band error values, and keeping the normal path out of `else`.

### google-decisions:returning-errors/signature — Returning errors: the error result
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:error-return · custom=concrete-error-return
- **rule:** Signal that a function can fail with an `error` result, by convention the last one.
  Exported functions return the `error` interface, not a concrete error type: a nil concrete
  pointer wrapped in an interface becomes a non-nil error. A function taking a
  `context.Context` should usually return an `error`, so callers can tell it was cancelled.
- **look for:** exported functions returning `*MyError`, `*os.PathError` or another concrete
  error type; functions that take a `ctx`, block or can fail, yet return no error.
- **skip:** `error` not last — revive reports it; functions whose job is to construct an error
  value; ctx-taking functions that cannot fail (e.g. reading values from the context).
- **example:** `func Open(name string) *os.PathError` -> `func Open(name string) error`

### google-decisions:returning-errors/results-on-error — Returning errors: other results on failure
- **meta:** severity=must · scope=body · check=llm
- **rule:** A nil error signals success. When a call returns a non-nil error, callers must treat
  the other results as unspecified unless the function documents otherwise; they are often zero
  values, but that cannot be assumed.
- **look for:** results used after the call failed (`v, err := f(); if err != nil {
  log(v.Name) }`); failure detected from a result instead of the error (`if v == nil` after an
  error-returning call); undocumented reliance on zero results.
- **skip:** documented partial results (`n` from `io.Reader.Read` or `io.Writer.Write`).

### google-decisions:error-strings — Error strings
- **meta:** severity=should · scope=body · check=lint+llm · lint=staticcheck:ST1005
- **rule:** Error strings are not capitalized (unless they begin with an exported name, a proper
  noun or an acronym) and do not end with punctuation, because they are usually embedded in
  other context before reaching the user. Full displayed messages (logs, test failures, API
  responses, UI) are another matter and are typically capitalized.
- **look for:** capitalized or punctuated text in error constructors ST1005 does not inspect
  (`errors.Wrap`, `status.Errorf`, custom `New…Error` helpers, `Error()` methods returning fixed
  text, non-constant formats); capitalized one-word messages; a trailing `?`.
- **skip:** constant strings in `errors.New`/`fmt.Errorf` (ST1005 reports them); messages that
  start with an exported identifier, proper noun or acronym; log and UI messages.
- **example:** `fmt.Errorf("Something bad happened.")` -> `fmt.Errorf("something bad happened")`

### google-decisions:handle-errors — Handle errors
- **meta:** severity=should · scope=body · check=lint+llm · lint=errcheck,nilerr
- **rule:** Make a deliberate choice for every error: handle it immediately, return it to the
  caller, or, in exceptional situations, call `log.Fatal` or (if absolutely necessary) `panic`.
  Discarding an error with `_` is rarely appropriate; when it is safe (e.g.
  `(*bytes.Buffer).Write`, documented never to fail), a comment should explain why.
- **look for:** errors assigned to `_` without a justifying comment (`_ = f.Close()`,
  `n, _ := w.Write(b)`) — errcheck ignores blank assignments; errors that are checked but then
  dropped (empty `if err != nil {}`, or the code carries on as if the call succeeded).
- **skip:** unchecked calls errcheck reports; `return nil` inside `if err != nil` (nilerr);
  commented discards of errors documented never to occur.
- **example:** `n, _ := b.Write(p)` -> `n, _ := b.Write(p) // never returns a non-nil error`

### google-decisions:in-band-errors — In-band errors
- **meta:** severity=should · scope=body · check=lint+llm · lint=nilnil
- **rule:** Do not signal errors or missing results with special values (-1, nil, "") that
  callers must remember to check. Return an additional, final result instead: an `error`, or a
  `bool` (`ok`) when no explanation is needed, so misuse such as `Parse(Lookup(key))` fails to
  compile. Some standard-library functions (package `strings`) use in-band values; new code
  should return additional values.
- **look for:** docs or code saying "returns -1 / "" / nil if not found"; index-style `int`
  results using `-1` for absent; an empty string or zero struct with a nil error meaning
  "missing".
- **skip:** `return nil, nil` pairs (nilnil reports them); comparators returning -1/0/1, which
  are values, not error signals.
- **example:** `func Lookup(key string) int // -1 if absent` -> `func Lookup(key string) (value int, ok bool)`

### google-decisions:indent-error-flow — Indent error flow
- **meta:** severity=should · scope=body · check=lint+llm · lint=revive:indent-error-flow,revive:superfluous-else,revive:early-return
- **rule:** Handle errors, and any condition that ends in `return`, `continue`, `panic` or
  `log.Fatal`, first; the normal path then continues unindented after the `if`, not in an
  `else`. If a variable from an `if` initializer is needed for more than a few lines, declare it
  before the `if` rather than keeping that code inside the `if`.
- **look for:** `if err != nil { handle } else { normal }` where the error branch does not
  terminate (make it return, then outdent); `if err == nil { long normal path }` with handling
  after it; `if v, err := f(); err == nil { many lines using v }`.
- **skip:** an `else` after a terminating branch and invertible `if … else { return }` — revive
  reports them.
- **example:** `if err != nil { log(err) } else { use(x) }` -> `if err != nil { log(err); return }` then `use(x)`
