# Google Go Style Best Practices — Documentation

What doc comments should say about parameters, contexts, concurrency, cleanup and errors, how
godoc formats them, and when a comment should boost an unusual line of code.

### google-practices:documentation-conventions-params — Document only non-obvious parameters
- **meta:** severity=consider · scope=body · check=llm
- **rule:** Not every parameter, struct field or option needs to be listed in the docs. Document
  the error-prone or non-obvious ones and say why they are interesting, writing for the likely
  audience (maintainers, newcomers, external users, yourself in six months).
- **look for:** doc comments that restate parameters (`format is the format, and data is the
  interpolation data`); undocumented surprises such as units, valid ranges, the meaning of nil or
  zero, mutation of arguments, option defaults and interactions.
- **skip:** obvious parameters left undocumented.

### google-practices:documentation-conventions-contexts — Document unusual context behavior
- **meta:** severity=should · scope=body · check=llm
- **rule:** That cancelling a context argument interrupts the function (which then returns
  `ctx.Err()` if it returns an error) is implied and need not be restated. Do document behavior
  that differs: another error (or nil) on cancellation; other mechanisms that interrupt the
  function or affect its lifetime (a `Stop` method, asynchronous shutdown); special expectations
  about the context's lifetime, lineage or attached values — and avoid APIs that make such demands.
- **look for:** functions that return nil on cancellation, keep working after the context ends,
  or need a context without a deadline or carrying a specific value, with no doc saying so;
  boilerplate such as "returns an error when the context is cancelled".

### google-practices:documentation-conventions-concurrency — Document non-obvious concurrency safety
- **meta:** severity=should · scope=body · check=llm · custom=undocumented-sync
- **rule:** Readers assume read-only operations are safe for concurrent use and mutating ones are
  not, so don't restate either. Document concurrency when it is unclear whether an operation is
  read-only (an LRU cache `Lookup` mutates), when the API provides synchronization (once on the type
  if it covers the whole type), and when the API consumes user-implemented interfaces with
  concurrency requirements (state them on the interface).
- **look for:** types guarded by an internal mutex or atomics whose doc doesn't say they are safe
  for concurrent use; accessor-like methods that mutate (caches, lazy init, cursors) without a
  warning; interfaces called from several goroutines without saying so; redundant safety remarks
  on plain getters and setters.

### google-practices:documentation-conventions-cleanup — Document cleanup requirements
- **meta:** severity=should · scope=body · check=llm · custom=undocumented-cleanup
- **rule:** Document every explicit cleanup the API requires (that the caller must call `Stop` or
  `Close`, and when); otherwise callers leak resources. If how to clean up may be unclear, explain
  it, for example with a short usage snippet (`defer resp.Body.Close()`).
- **look for:** constructors or methods returning values with `Close`/`Stop`/`Release`/`Shutdown`
  methods, cancel funcs, or bodies to close, whose docs don't tell the caller to call them.
- **example:** `// NewTicker returns a new Ticker.` -> `// ... Call Stop to release the Ticker's associated resources when done.`

### google-practices:documentation-conventions-errors — Document the errors a function returns
- **meta:** severity=should · scope=body · check=llm · custom=undocumented-sentinel
- **rule:** Document significant sentinel errors and error types a function returns, so callers
  know which conditions they can handle ("At end of file, Read returns 0, io.EOF"). Say whether an
  error type comes as a pointer (`*PathError`), since `errors.Is`, `errors.As` and `cmp` depend on
  it. Put conventions that hold for most errors of a package in the package doc.
- **look for:** exported functions returning a package sentinel or error type (directly or via
  `%w`) that their doc doesn't mention; docs naming `PathError` when `*PathError` is returned; a
  package whose errors share one type with no package-level note.
- **skip:** don't suggest changing the result to the concrete error type: it stays `error` (nil
  interface pitfall).

### google-practices:godoc-formatting — Godoc formatting
- **meta:** severity=consider · scope=body · check=llm · custom=doc-code-unindented · overlaps=google-decisions:commentary, google-decisions:examples
- **rule:** Use godoc syntax: a blank `//` line separates paragraphs; indented lines (two extra
  spaces in the guide) render verbatim — use that for code and for lists or tables godoc cannot
  format; a single capitalized line without punctuation (except parentheses and commas) followed
  by a paragraph renders as a heading. Runnable examples in test files attach to the docs and are
  often better than code in comments.
- **look for:** code or command lines in doc comments written flush with the text (they get
  reflowed); paragraphs not separated by a blank comment line; long code samples in comments that
  would work as an `ExampleXxx` test.
- **note:** Go 1.19 added native lists and `# Heading` syntax to doc comments; gofmt now rewrites
  implicit headings to `#` form and re-indents code blocks with a tab.

### google-practices:signal-boost — Comment code that looks like an idiom but isn't
- **meta:** severity=consider · scope=body · check=llm · custom=err-nil-unboosted · overlaps=google-guide:concision
- **rule:** When a line looks like a common idiom but differs subtly — the classic case is
  `err == nil` where readers expect `err != nil` — add a comment that draws attention to the
  difference.
- **look for:** `if err == nil {` or `if err := f(); err == nil {` without a comment; other
  near-copies of common idioms with an inverted or unusual detail.
- **example:** `if err := doSomething(); err == nil {` -> `if err := doSomething(); err == nil { // if NO error`
