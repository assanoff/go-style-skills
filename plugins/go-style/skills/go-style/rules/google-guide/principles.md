# Google Go Style Guide — Style principles

The five attributes of readable Go code, in order of importance: clarity, simplicity,
concision, maintainability and consistency — consistency only breaks ties and never
overrides the others.

### google-guide:clarity-purpose — What is the code actually doing?
- **meta:** severity=should · scope=body · check=lint+llm · lint=gocognit
- **rule:** Clarity is judged by the reader, not the author: code should be easy to read
  rather than easy to write, and it should be easy to see what it does. Where a reader
  may be uncertain or need prior knowledge, invest in making the purpose clear — more
  descriptive names, extra comments, whitespace and comments that break the code into
  steps, or extraction into separate functions.
- **look for:** gocognit hotspots and long functions running several steps together with
  no blank line, comment or helper call marking them; terse names (`d`, `tmp2`, `res`)
  for values used across many lines; dense expressions or call chains whose intent must
  be decoded; logic relying on an invariant or protocol stated nowhere nearby.
- **skip:** the complexity score itself — gocognit reports it; name the concrete obstacle.
  Flat runs of simple checks that read easily despite a high score.

### google-guide:clarity-rationale — Why is the code doing what it does?
- **meta:** severity=should · scope=body · check=llm
- **rule:** When names don't convey why code does something, comment it — above all for
  nuances a reader may not know (language subtleties, business-logic distinctions, APIs
  needing care, code made intricate for performance, unexpected type conversions).
  Explain why, not what: comments that restate, contradict or clutter the code hurt, and
  self-describing names beat redundant comments. Reserve unfamiliar patterns for code
  that needs them (typically performance), so they signal where readers must focus.
- **look for:** non-obvious code with no "why" — unusual patterns (buffer reuse, `unsafe`,
  bit tricks), surprising numeric conversions, magic values and special cases,
  order-dependent steps, subtle auth checks, a closure using a variable declared far
  away; comments that narrate the code (`i++ // increment i`) or contradict it.
- **skip:** self-explanatory code; doc-comment form (google-decisions commentary rules).
- **note:** the guide's loop-variable example predates Go 1.22 per-iteration loop variables.

### google-guide:simplicity — Simplicity
- **meta:** severity=should · scope=body · check=lint+llm · lint=nestif
- **rule:** Write code the simplest way that meets its behavior and performance goals:
  readable top to bottom, not assuming the reader already knows what it does or
  remembers all preceding code, no needless abstraction layers, plain names for mundane
  things, a visible flow of values and decisions; "clever" code rarely qualifies. Add
  complexity deliberately (performance, many disparate clients) with docs, tests and
  examples; code that is complex when its purpose is simple should be reworked.
- **look for:** nestif hotspots and arrow code that early returns would flatten; a flag or
  state variable set in one branch and consumed far below; wrappers or layers that only
  forward calls; clever one-liners, nested closures or generic tricks where plain
  statements would do; performance tricks (buffer reuse, pooling) with no comment or
  benchmark justifying them.
- **skip:** documented, justified complexity; extra implementation work that makes an API
  easier to call correctly, or the reverse — the guide accepts both trade-offs.

### google-guide:least-mechanism — Least mechanism
- **meta:** severity=should · scope=body · check=lint+llm · lint=exptostd · custom=flag-set-in-test
- **rule:** Of several ways to express an idea, use the most standard tool: a core language
  construct (channel, slice, map, loop, struct) if it suffices, else the standard library,
  else a library already established in the codebase, and only then a new dependency or
  your own code. Sophisticated machinery needs a reason — complexity is easy to add and
  hard to remove.
- **look for:** goroutines, channels, `select`, `sync.Once` or atomics where a plain value
  or mutex suffices; reflection where a concrete type, small interface or generics works;
  set, collection or functional-helper libraries where `map[K]bool`, a loop or
  `slices`/`maps` works; hand-rolled std helpers; registries or factories for one case;
  tests calling `flag.Set` instead of assigning the flag-bound variable.
- **skip:** `flag.Set` in tests of the CLI itself; set libraries for operations impossible or
  overly complicated with a map; x/exp imports with std equivalents — exptostd reports.
- **example:** `seen := sets.New[string]()` -> `seen := map[string]bool{}`

### google-guide:concision — Concision
- **meta:** severity=consider · scope=body · check=lint+llm · lint=dupl · custom=err-nil-boost
- **rule:** Keep the signal-to-noise ratio high so the relevant details stand out: avoid
  repetitive code, extraneous syntax, opaque names, unnecessary abstraction and noisy
  whitespace, and lean on common idioms readers recognize at a glance. Structure code so
  the important details are most apparent; when code resembles an idiom but differs
  subtly (e.g. `err == nil`), boost the signal with a comment.
- **look for:** near-identical blocks or tests differing in a value or two (factor into a
  helper or a table-driven test whose table holds just what varies); redundant
  conversions, parentheses or temporaries; wrappers adding no meaning; an idiom
  look-alike such as `if err := f(); err == nil {` with no comment flagging it.
- **skip:** the duplicate-fragment finding itself — dupl reports it.
- **example:** `if err := f(); err == nil {` -> `if err := f(); err == nil { // if NO error`

### google-guide:maintainability/design — Maintainability: design for change
- **meta:** severity=should · scope=decl · check=lint+llm · lint=unused
- **rule:** Code is edited far more often than written, so make it easy to modify
  correctly: APIs that can grow gracefully, explicit assumptions, abstractions that map
  to the problem rather than the code's structure, no unnecessary coupling, no unused
  features. Interfaces and extra types hide information, so they must earn it, and
  implementation specifics needed to use an interface correctly must be documented on it
  or at the call site; easier, safer future change is worth a bit of design complexity.
- **look for:** an interface or wrapper type with one implementation and no consumer
  needing substitution; abstractions mirroring code layout (base structs for reuse, a
  layer per framework step) rather than domain concepts; exported options, parameters or
  methods nobody uses; unstated preconditions (non-nil, sorted, lock held); a god object
  passed to read one field; exported signatures that must break to gain an option.
- **skip:** unexported dead code — `unused` reports it; interface specifics belong to
  google-decisions:interfaces and google-practices:avoid-unnecessary-interfaces.

### google-guide:maintainability/tests — Maintainability: test suite
- **meta:** severity=should · scope=test · check=llm
- **rule:** Maintainable code has a comprehensive test suite that keeps promised behavior
  and important logic correct, with clear, actionable diagnostics when a test fails.
- **look for:** new or changed non-trivial logic (branching, parsing, error paths,
  concurrency) that no test exercises; behavior promised in doc comments with no test;
  failures that don't say what was called, with which input, and what was got vs wanted.
- **skip:** trivial plumbing, renames and generated code; failure-message details belong to
  google-decisions:useful-test-failures and related testing rules.

### google-guide:maintainability/hidden-details — Maintainability: easy-to-miss details
- **meta:** severity=should · scope=body · check=lint+llm · lint=gocritic:sloppyReassign,gocritic:boolExprSimplify~![(]|!! · custom=if-init-assign
- **rule:** Don't hide important details where they are easy to overlook — a lone `=` vs
  `:=`, a `!` inside a long condition, an edge case buried in a helper. Such code isn't
  wrong, but write it more explicitly (separate statements, named sub-expressions) or
  add a comment that calls attention to the behavior.
- **look for:** `if x, err = f(); err != nil` assigning outer variables in an if/switch init
  (sloppyReassign catches only single-value forms); `:=` in an inner block shadowing a
  variable the code meant to update; `!` or negations buried in compound booleans; a
  helper whose innocuous name hides validation, filtering or a special case callers must
  account for.
- **skip:** such constructs already called out by a comment.
- **example:** `if user, err = db.UserByID(id); err != nil {` -> `u, err := db.UserByID(id)`
  + `if err != nil {...}` + `user = u`

### google-guide:maintainability/predictable-names — Maintainability: predictable names
- **meta:** severity=should · scope=decl · check=llm · custom=param-name-consistency
- **rule:** A user or maintainer should be able to predict the name of a variable, method or
  function in its context. Parameters and receivers for the same concept should
  typically share one name, keeping documentation coherent and refactoring cheap.
- **look for:** one concept named differently across a package's functions (`ctx`/`c`,
  `req`/`r`/`in`, `userID`/`uid`); method or constructor names that break the package's
  pattern (`NewX` beside `MakeY`, `Close` vs `Shutdown` for the same operation).
- **skip:** inconsistent receiver names — revive reports them under
  google-decisions:receiver-names; distinct roles of one type (`src`, `dst`).

### google-guide:maintainability/dependencies — Maintainability: minimal dependencies
- **meta:** severity=consider · scope=repo · check=llm
- **rule:** Minimize dependencies, explicit and implicit: fewer packages means less code that
  can change behavior, and not relying on internal or undocumented behavior avoids
  breakage when that behavior changes.
- **look for:** a new module or heavy package imported for a few lines of functionality;
  reliance on undocumented behavior (parsing error or `String()` text, map iteration
  order, unexported fields via `reflect`/`unsafe`, `//go:linkname`); implicit inputs read
  deep inside library code (environment variables, global registries).
- **skip:** standard-library imports; modules the project already uses for that purpose.

### google-guide:consistency — Consistency
- **meta:** severity=consider · scope=repo · check=llm · conflicts=uber:be-consistent
- **rule:** Code should look, feel and behave like similar code in the codebase, the team
  or package, and the file; consistency within a package matters most. It never
  overrides the principles above or documented style, and package consistency doesn't
  override global consistency — it breaks ties.
- **look for:** one concept with several names in a file or package (`acct`, `account`,
  `a`); the same problem solved several ways in one package (two error-construction
  styles, two option patterns); new code ignoring a pattern the package applies
  consistently.
- **skip:** guide-conforming code that differs from a local deviation — consistency is no
  reason to copy the deviation.
- **note:** Uber puts consistency "above all else"; Google ranks it last.
