# Effective Go — Control Structures and Functions

How Effective Go writes `if`, `:=` redeclaration, `for`, `switch` and type switches,
and how functions use multiple and named results and `defer`.

### effective:if — If
- **meta:** severity=should · scope=body · check=lint+llm · lint=revive:indent-error-flow,revive:superfluous-else,revive:early-return · overlaps=google-decisions:indent-error-flow
- **rule:** When an `if` body doesn't flow into the next statement — it ends in `break`,
  `continue`, `goto` or `return` — omit the unnecessary `else`. Guard against error
  conditions as they arise and return early, so the successful flow of control runs
  down the page.
- **look for:** the success path nested in `if err == nil { ... }` with the failure
  handled afterwards; error checks postponed past unrelated work.
- **skip:** `else` after a terminating `if` and invertible `if/else` blocks — revive
  reports them.
- **example:** `if err != nil { return err } else { codeUsing(f) }` -> `if err != nil { return err }` then `codeUsing(f)`

### effective:redeclaration — Redeclaration and reassignment
- **meta:** severity=consider · scope=body · check=llm · overlaps=google-practices:shadowing
- **rule:** A `:=` may list an already declared variable such as `err` and merely
  reassign it, but only in the same scope and only if at least one other variable is
  new; in an inner scope it declares a new variable that shadows the outer one.
  Parameters and results share the scope of the function body.
- **look for:** `v, err := f()` inside an `if`/`for`/`switch` block when the outer
  `err` or a named result is checked or returned after the block; outer variables
  left stale because the block assigned a shadow.
- **skip:** shadows never read after their block; bare returns of a shadowed named
  result — the compiler rejects them.
- **example:** `if c { v, err := f() }` (outer `err` unchanged) -> declare `v` before the block, then `v, err = f()`

### effective:for — For
- **meta:** severity=consider · scope=body · check=lint+llm · lint=revive:range
- **rule:** Let a `range` clause manage loops over arrays, slices, strings and maps and
  reads from a channel. If only the key or index is needed, drop the second variable
  (`for key := range m`); if only the value, discard the index with `_`. Ranging over
  a string yields runes decoded from UTF-8 (bad bytes become U+FFFD). Several loop
  variables use parallel assignment (`i, j = i+1, j-1`).
- **look for:** `for i := 0; i < len(s); i++` loops that only read `s[i]`; byte-wise
  indexing of a string where characters are meant.
- **skip:** `for k, _ := range` — revive and gofmt -s report it; index loops that need
  the index arithmetic.
- **note:** Since Go 1.22 each iteration has its own loop variables and `range`
  accepts integers (`for i := range n`); since Go 1.23 it accepts iterator functions.

### effective:switch/if-else-chains — Switch: expressionless switch for if-else chains
- **meta:** severity=consider · scope=body · check=lint+llm · lint=gocritic:ifElseChain,gocritic:switchTrue
- **rule:** A `switch` with no expression switches on `true` and evaluates its cases top
  to bottom until one matches, so writing an if-else-if-else chain as a `switch` is
  possible and idiomatic.
- **look for:** if-else-if chains that gocritic skips because one of their `if`s has
  an init statement.
- **skip:** chains of three or more branches without init statements, and
  `switch true {` — gocritic reports them.
- **example:** `if x < 0 {...} else if x == 0 {...} else {...}` -> `switch { case x < 0: ...; case x == 0: ...; default: ... }`

### effective:switch/break — Switch: no fall-through, break and labels
- **meta:** severity=should · scope=body · check=lint+llm · lint=revive:useless-break,revive:useless-fallthrough,staticcheck:SA4011 · custom=empty-case-clause · overlaps=google-decisions:switch-break
- **rule:** Cases don't fall through, so no trailing `break` is needed, and values that
  share a body go in one comma-separated list (`case ' ', '?', '&':`). A `break`
  inside a `switch` ends only the switch; to leave an enclosing loop, label the loop
  and `break Label`. `continue` also takes a label but applies only to loops.
- **look for:** an empty `case` written as if it fell into the next one (in Go it does
  nothing); a `break` inside a `switch` in a loop where the intent is to exit the
  loop.
- **skip:** a trailing `break`, a lone `fallthrough` and `break` statements with no
  effect — the listed linters report them.
- **example:** `case 'a':` (empty) followed by `case 'b': f()` -> `case 'a', 'b': f()`

### effective:type_switch — Type switch
- **meta:** severity=consider · scope=body · check=lint · lint=gocritic:typeSwitchVar,staticcheck:S1034
- **rule:** Bind the value in a type switch (`switch t := t.(type)`): in each clause the
  variable has that clause's type, so cases need no further assertions. Reusing the
  original name is idiomatic.
- **skip:** type switches that only branch on the type and never use the value.
- **example:** `switch v.(type) { case int: n := v.(int) }` -> `switch v := v.(type) { case int: n := v }`

### effective:multiple-returns — Multiple return values
- **meta:** severity=should · scope=decl · check=llm · custom=pointer-out-param · overlaps=google-decisions:in-band-errors
- **rule:** Use multiple results instead of C's clumsy idioms: return a value plus an
  error (as `Write` returns `n` and `err`) rather than in-band error values such as
  `-1` for EOF, and return extra values rather than passing a pointer to simulate a
  reference parameter.
- **look for:** sentinel results that signal failure or absence (`-1`, `""`, `nil`
  without an error) and docs like "returns -1 if ..."; pointer parameters that are
  only written (`func parse(s string, out *int) bool`).
- **skip:** APIs that decode into or register a caller's variable (`json.Unmarshal`,
  `flag.IntVar`); conventional in-band results such as `strings.Index`.
- **example:** `func nextInt(b []byte, pos *int) int` -> `func nextInt(b []byte, i int) (int, int)`

### effective:named-results — Named result parameters
- **meta:** severity=consider · scope=decl · check=lint+llm · lint=revive:confusing-results · overlaps=google-decisions:named-result-parameters
- **rule:** Result names are optional but act as documentation: name results when it
  isn't obvious which returned value is which, as with several results of one type
  (`(value, nextPos int)`). Named results start at their zero values, and a bare
  `return` returns their current values, which can simplify short functions such as
  `io.ReadFull`.
- **look for:** results whose roles the types don't convey although the types differ
  or the repeats aren't adjacent (`(int, string, int)`).
- **skip:** adjacent unnamed results of the same type — revive reports them.
- **note:** Effective Go sets no limit on bare returns; Google allows them only in
  small functions, and `nakedret` enforces such a limit.

### effective:defer — Defer
- **meta:** severity=should · scope=body · check=lint+llm · lint=staticcheck:SA5001,govet:defers
- **rule:** Release a resource with `defer` right after acquiring it successfully
  (`defer f.Close()`, `defer mu.Unlock()`): every return path, including ones added
  later, then releases it, and the release sits next to the acquisition. A deferred
  call's arguments, including a method's receiver, are evaluated when the `defer`
  executes, not when the call runs; deferred calls run in LIFO order when the
  function (not the enclosing block) returns.
- **look for:** `Close`/`Unlock` at the end of a function or repeated before each
  `return`; deferred arguments meant to reflect state at exit (`defer log.Print(n)`
  while `n` still changes) instead of a deferred closure; a `defer` in a loop, which
  holds every iteration's resource until the function returns.
- **skip:** `defer x.Close()` before the error check (staticcheck SA5001) and deferred
  `time.Since` arguments (vet `defers`) — linters report them.
