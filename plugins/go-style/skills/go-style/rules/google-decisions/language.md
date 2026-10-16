# Google Style Decisions — Language

Language-level decisions: composite literal layout, nil slices, where not to break lines in signatures, calls and conditionals, copying, panics and Must helpers, goroutine lifetimes, interfaces, generics, receivers, and small idioms (`switch`/`break`, aliases, `%q`, `any`).

### google-decisions:literal-formatting — Literal formatting
- **meta:** severity=should · scope=body · check=llm · custom=field-by-field-init
- **rule:** Where possible, build a value with one composite literal instead of declaring it and
  assigning its fields one by one. gofmt lays literals out well; the sub-rules below cover
  what it leaves undecided.
- **look for:** `var x T`, `x := T{}`, `x := &T{}` or `new(T)` followed directly by a run of
  `x.Field = ...` assignments of values already known at that point.
- **skip:** fields set conditionally or from values computed between the assignments; types
  whose fields cannot be set in a literal (unexported fields, setter-only APIs).
- **example:** `var r csv.Reader; r.Comma = ','; r.Comment = '#'` ->
  `r := csv.Reader{Comma: ',', Comment: '#'}`

### google-decisions:literal-field-names/external — Field names: types from other packages
- **meta:** severity=must · scope=body · check=lint · lint=govet:composites
- **rule:** Struct literals of types defined outside the current package must use field names.
  Field order and the full field set are not part of a struct's public API, so positional
  literals couple the caller to them.
- **skip:** reported by govet composites, including `&pkg.T{...}` and elided `[]pkg.T{{...}}`.
- **note:** composites whitelists a few std types (`image.Point`, `color.RGBA`, …) that the
  guide does not exempt.
- **example:** `csv.Reader{',', '#', 4, false}` ->
  `csv.Reader{Comma: ',', Comment: '#', FieldsPerRecord: 4}`

### google-decisions:literal-field-names/local — Field names: package-local types
- **meta:** severity=should · scope=body · check=llm · custom=unkeyed-local-literal
- **rule:** For package-local types field names are optional, but use them whenever they make
  the code clearer, which is common; a struct with many fields should almost always be
  initialized with field names.
- **look for:** positional literals of local structs with many fields (roughly four or more)
  or with adjacent same-typed values whose meaning is not obvious (`opts{true, false, 3}`).
- **skip:** short, obvious literals (`Type{42}`, `point{x, y}`); types from other packages
  (literal-field-names/external).
- **example:** `o := options{true, false, 3, "x"}` ->
  `o := options{verbose: true, retries: 3, name: "x"}`

### google-decisions:literal-matching-braces — Matching braces
- **meta:** severity=should · scope=body · check=llm · custom=literal-closing-brace
- **rule:** The closing brace of a literal sits on a line with the same indentation as the line
  of its opening brace, as with functions and `if` blocks. In a multi-line literal, end the
  last element with a comma and put the closing brace on the next line; gofmt does not fix it.
- **look for:** a closing brace sharing a line with the last element (`{Key: "line"}}`); an
  element opened with `{` and a newline but closed on its value line (`Key: "value"},`).
- **skip:** one-line literals; cuddled literals that follow literal-cuddled-braces.
- **note:** gofumpt rewrites these cases, but its "File is not properly formatted" report
  cannot be attributed to this rule.
- **example:** `{Key: "multi"},⏎    {Key: "line"}}` -> `{Key: "multi"},⏎    {Key: "line"},⏎}`

### google-decisions:literal-cuddled-braces — Cuddled braces
- **meta:** severity=should · scope=body · check=llm · custom=literal-cuddle
- **rule:** Cuddling braces (dropping the whitespace between them, `[]*T{{` … `}, {` … `}}`) in
  slice and array literals is allowed only when the indentation still matches and every
  inner value is itself a literal or a proto builder, not a variable or other expression.
- **look for:** cuddled closings (`}}`) after an element list that mixes in variables or
  calls (`first, {` … `}}`); cuddled literals whose element lines are mis-indented.
- **skip:** uncuddled multi-line literals; cuddled lists of literals or
  `pb.T_builder{...}.Build()` values.
- **example:** `[]*T{⏎    first,⏎    {⏎        Field: "second",⏎    }}` -> `…⏎    },⏎}`

### google-decisions:literal-repeated-type-names — Repeated type names
- **meta:** severity=consider · scope=body · check=llm
- **rule:** Repeated element and key type names may be omitted from slice and map literals to
  reduce clutter (`gofmt -s` does this). Spelling them out is reasonable for a complex type
  that is uncommon in the project, when the repetitions are far apart and remind the reader
  of the context.
- **look for:** `[]*T{&T{...}, &T{...}}`, `[]T{T{...}}`, `map[K]*V{K{...}: &V{...}}` with a
  simple, familiar type.
- **skip:** complex or unusual types in long literals; projects running gofmt with simplify
  (golangci `gofmt` formatter, `simplify: true`) get these as formatting issues.
- **example:** `[]*Type{&Type{A: 42}, &Type{A: 43}}` -> `[]*Type{{A: 42}, {A: 43}}`

### google-decisions:literal-zero-value-fields — Zero-value fields
- **meta:** severity=consider · scope=body · check=llm
- **rule:** Zero-value fields may be omitted from struct literals when clarity is not lost;
  APIs designed for zero-value construction read better when only the options actually set
  are listed.
- **look for:** literals spelling out `nil`, `0`, `false` or `""` for fields that do not
  matter to the call, often under a "these are defaults" comment.
- **skip:** zero values that carry meaning at the call site (an explicit `Retries: 0` that
  disables retries).
- **example:** `&db.Options{BlockSize: 1 << 16, Comparer: nil, MaxOpenFiles: 0}` ->
  `&db.Options{BlockSize: 1 << 16}`

### google-decisions:literal-zero-value-fields/tests — Zero-value fields in table tests
- **meta:** severity=consider · scope=test · check=llm
- **rule:** Non-trivial table-test case structs benefit from field names, so each case can omit
  the zero-valued fields unrelated to it (successful cases omit error and failure fields);
  when the zero value is what makes the case understandable (zero or `nil` inputs), name it.
- **look for:** success cases that still list `wantErr: nil`/`false`; rows padded with zero
  values for fields the case does not exercise; zero/nil-input cases that leave the decisive
  field implicit.
- **skip:** zero values that are the expectation under test (`wantIPv6: false` next to
  `wantIPv4: true`); small tables with a few self-explanatory positional fields.
- **example:** `{input: "1.2.3.4", wantPieces: []string{...}, wantErr: nil}` -> drop `wantErr: nil`

### google-decisions:nil-slices/local-var — Nil slices: local declarations
- **meta:** severity=should · scope=body · check=lint · lint=revive:enforce-slice-style
- **rule:** Declare an empty local slice as nil (`var t []string`), especially when it may become
  a return value, rather than `[]string{}` or `make([]string, 0)`: `len`, `cap`, `range` and
  `append` all work on nil slices, and nil reduces the risk of bugs in callers.
- **skip:** reported by revive enforce-slice-style (style `nil`), which also flags empty
  literals in returns and arguments but not `make([]T, 0, n)`; dismiss hits where an external
  format needs a non-nil empty slice (JSON `[]` vs `null`).
- **example:** `t := []string{}` -> `var t []string`

### google-decisions:nil-slices/api — Nil slices: APIs and emptiness checks
- **meta:** severity=should · scope=body · check=llm · custom=slice-nil-compare
- **rule:** Do not design APIs that force callers to tell a nil slice from an empty one (nil
  for "error", empty for "no results"); report failures with an `error`. Implementations
  treat both as empty by checking `len(s) == 0`, not `s == nil`, because which one a producer
  returns in the empty case can change silently and cause subtle bugs.
- **look for:** doc comments giving nil and empty slices different meanings; `s == nil` /
  `s != nil` as the emptiness test on slice parameters or results; nil vs `[]T{}` returned to
  encode state.
- **skip:** `s != nil && len(s) > 0` — redundant (staticcheck S1009) but not a violation.
- **example:** `if s == nil { return }` -> `if len(s) == 0 { return }`

### google-decisions:indentation-confusion — Indentation confusion
- **meta:** severity=should · scope=body · check=llm · overlaps=google-guide:line-length
- **rule:** Avoid a line break that lines the rest of the line up with the indented block that
  follows (wrapped `if`/`for`/`switch` headers, function signatures). If it is unavoidable,
  leave a space between the wrapped line and the block's code (a blank line, as in the
  guide's long-`case` example).
- **look for:** continuation lines of a block header indented exactly like the first
  statement of the block below it.
- **skip:** closures and multi-line literals inside a header whose braces match (see
  conditional-formatting/line-breaks).
- **example:** `if cond1 && cond2 &&⏎    cond3 && cond4 {⏎    log.Info(...)` -> extract the
  conditions into locals or keep the header on one line

### google-decisions:func-formatting/signature — Function formatting: signatures
- **meta:** severity=should · scope=body · check=llm · custom=multiline-signature · overlaps=google-guide:line-length · conflicts=uber:avoid-overly-long-lines
- **rule:** Keep a function or method declaration's signature on a single line, even when long:
  a wrapped parameter list lines up with the body and causes indentation confusion. Shorten
  the signature instead (fewer parameters, an option struct; see best-practices#funcargs).
- **look for:** parameter or result lists split across lines, including the
  one-parameter-per-line form with `) {` on its own line.
- **skip:** function literals (the rule names declarations).
- **note:** gofumpt and many open-source codebases accept wrapped signatures; this guide does
  not, and Uber's advice to wrap before 99 columns contradicts it.
- **example:** `func (r *T) Name(foo1, foo2 string,⏎    foo3 int) {` ->
  `func (r *T) Name(foo1, foo2 string, foo3 int) {`

### google-decisions:func-formatting/calls — Function formatting: calls and long strings
- **meta:** severity=should · scope=body · check=llm · custom=split-string-literal · overlaps=google-guide:line-length · conflicts=uber:avoid-overly-long-lines
- **rule:** Do not break a call's argument list based solely on line length: shorten it by
  factoring out locals, or let it stay long. Line breaks are always fine when they aid
  understanding (an API you cannot change, an unusual call) and follow semantic groups of
  arguments rather than a column. Do not split long string literals to fit; break after the
  format string and put the arguments on the following lines.
- **look for:** argument lists wrapped mid-list at an arbitrary column; string literals split
  with `+` across lines; continuation lines that mix unrelated argument groups.
- **skip:** calls broken into meaningful groups (one vertex per line, a format string followed
  by its grouped arguments).
- **example:** `bad := foo.Call(long, list, of, parameters,⏎    with, arbitrary, line, breaks)`
  -> one line, or extract locals

### google-decisions:func-formatting/arg-comments — Function formatting: inline argument comments
- **meta:** severity=should · scope=body · check=llm · custom=inline-arg-comment · conflicts=uber:avoid-naked-parameters
- **rule:** Avoid inline comments on individual call arguments where possible; use an option
  struct, or put the detail in the function's documentation.
- **look for:** `/* name */` or trailing `// name` comments labelling arguments inside a call.
- **skip:** calls into APIs you cannot change where no clearer form exists (the guide says
  "where possible").
- **note:** Uber recommends exactly these `/* isLocal */` comments for naked parameters.
- **example:** `server.New(⏎    ctx,⏎    42, // Port⏎)` ->
  `server.New(ctx, server.Options{Port: 42})`

### google-decisions:conditional-formatting/line-breaks — Conditionals and loops: no artificial line breaks
- **meta:** severity=should · scope=body · check=llm · custom=multiline-condition · overlaps=google-guide:line-length · conflicts=uber:avoid-overly-long-lines
- **rule:** Do not line-break `if` conditions, `for` clauses, or `switch`/`case` lines. Extract
  boolean operands (when short-circuiting is not needed) or repeated subexpressions into
  locals, move a loop condition into the body with `break`, or let the line stay long.
  Closures and multi-line literals in an `if` are fine when their braces match. If a case
  list is excessively long, put every value on its own indented line and add a blank line
  before the clause body.
- **look for:** conditions continued with `&&`/`||` on the next line; `case a,⏎    b:` lists;
  wrapped `for` headers; the same call repeated inside one condition.
- **skip:** `if err := f(func() error {` … `}); err != nil {` and literal arguments with
  matching braces; the fully indented long-case form followed by a blank line.
- **example:** `if db.InTx() &&⏎    db.KeysMatch(k) {` ->
  `inTx := db.InTx()⏎match := db.KeysMatch(k)⏎if inTx && match {`

### google-decisions:conditional-formatting/yoda — Conditionals: variable on the left
- **meta:** severity=should · scope=body · check=lint+llm · lint=staticcheck:ST1017,gocritic:yodaStyleExpr · custom=yoda-const
- **rule:** When comparing a variable with a constant, put the variable on the left of the
  equality operator; constant-first ("Yoda") conditions read less clearly.
- **look for:** named constants or enum values on the left (`if StatusDone == s`).
- **skip:** a literal or `nil` on the left — staticcheck ST1017 and gocritic yodaStyleExpr
  report it; ordering comparisons (`0 < n`), which the guide does not address.
- **example:** `if "foo" == result {` -> `if result == "foo" {`

### google-decisions:copying/sync — Copying: synchronization values
- **meta:** severity=must · scope=decl · check=lint · lint=govet:copylocks
- **rule:** Synchronization objects such as `sync.Mutex`, and structs containing them, must not
  be copied — not by assignment, value parameters or receivers, returns, or range variables;
  take and return pointers to types that hold them.
- **skip:** reported by govet copylocks (also `sync.WaitGroup`, `sync.Once`, `sync/atomic`
  types and other `noCopy` types).
- **example:** `func (c Counter) Inc()` with `mu sync.Mutex` in Counter ->
  `func (c *Counter) Inc()`

### google-decisions:copying/pointer-methods — Copying: types with pointer methods
- **meta:** severity=should · scope=body · check=llm · custom=copy-pointer-method-type
- **rule:** Be careful when copying a struct from another package: in general, do not copy a
  value of type `T` whose methods are on `*T` (a copied `bytes.Buffer` may alias the
  original's internal array). When authoring an API whose structs hold such fields, take and
  return pointers; value receivers and value parameters hide the copy.
- **look for:** `b2 := b1` or `*p` copies of `bytes.Buffer`, `strings.Builder` and other
  pointer-method types; value receivers or parameters of structs containing them;
  constructors returning `T` rather than `*T` for such structs.
- **skip:** lock types (govet copylocks, copying/sync); types documented as safe to copy.
- **example:** `func (r Record) Process()` with `buf bytes.Buffer` in Record ->
  `func (r *Record) Process()`

### google-decisions:dont-panic — Don't panic
- **meta:** severity=should · scope=body · check=llm · custom=panic-on-error · conflicts=uber:exit-in-main
- **rule:** Do not use `panic` for normal error handling; return an `error` as an extra result.
  In `package main` and initialization code, errors that should end the program (e.g. bad
  configuration) are better reported by exiting with a message and no stack trace (deferred
  calls do not run). For "impossible" conditions — bugs that review and tests should catch —
  a function may reasonably return an error or terminate with a fatal log.
- **look for:** `if err != nil { panic(err) }` or `panic(fmt.Sprintf(...))` in functions that
  could return an error; panics on user input, I/O or network failures.
- **skip:** Must functions; invariant or API-misuse panics and package-internal
  panic/recover (best-practices#when-to-panic); `panic("unreachable")` after a fatal call.
- **note:** `log.Exit` (no stack) and `log.Fatal` (stack trace) here are glog semantics; std
  `log.Fatal` exits without a stack trace. Uber allows exits only in `main()`.
- **example:** `if err != nil { panic(err) }` -> `if err != nil { return nil, err }`

### google-decisions:must-functions — Must functions
- **meta:** severity=should · scope=body · check=llm · custom=must-in-error-func
- **rule:** Setup helpers that stop the program on failure are named `MustXYZ`/`mustXYZ` and are
  called only early in program startup, typically to initialize package-level values
  (`template.Must`, `regexp.MustCompile`). Do not call them on user input, in request
  handlers, or wherever ordinary error handling is possible, even with some refactoring.
- **look for:** `MustX(...)` with runtime (non-constant) arguments in functions that return an
  `error` or serve requests; functions that panic on error and return a value without the
  `Must` prefix; `Must`-named functions that return an error instead of stopping.
- **skip:** Must calls with constant arguments in package-level vars, `init` or `main`.
- **example:** `v := version.MustParse(o.GetVersionString())` in a func returning `error` ->
  `v, err := version.Parse(o.GetVersionString()); if err != nil { return nil, err }`

### google-decisions:must-functions/tests — Must helpers in tests
- **meta:** severity=should · scope=test · check=llm · custom=must-helper-panics
- **rule:** Test helpers may use the `mustXYZ` convention when they stop only the current test:
  they take `t`, are marked with `t.Helper()`, and call `t.Fatal` on error. They are handy for
  creating values inline, e.g. in table-test struct fields.
- **look for:** test `must*` helpers that `panic` or `log.Fatal` instead of calling `t.Fatal`;
  must-style helpers in test files that take no `testing.TB`.
- **skip:** a missing `t.Helper()` — thelper reports it (mark-test-helpers).
- **example:** `func mustMarshalAny(m proto.Message) *anypb.Any {` … `panic(err)` ->
  `func mustMarshalAny(t *testing.T, m proto.Message) *anypb.Any {` … `t.Fatalf(...)`

### google-decisions:goroutine-lifetimes — Goroutine lifetimes
- **meta:** severity=should · scope=body · check=llm
- **rule:** When you spawn goroutines, make it clear when or whether they exit. Goroutines
  blocked on channels leak (the GC does not reclaim them); in-flight goroutines can race on
  inputs or send on closed channels, and unbounded lifetimes make memory use and tests
  unpredictable. Keep synchronization within one function's scope (`sync.WaitGroup` +
  `Wait`, context cancellation), factor logic into synchronous functions, and document when
  and why goroutines exit if it is still not obvious.
- **look for:** `go` statements with no join or stop path (no wait, done channel or ctx);
  goroutines started in loops or handlers that outlive the call; sends on unbuffered
  channels whose receiver may have returned early; undocumented long-lived workers.
- **skip:** goroutines whose bounded lifetime is evident in the same function.
- **example:** `for item := range w.q { go process(item) }` ->
  `wg.Add(1); go func() { defer wg.Done(); process(ctx, item) }()` plus `wg.Wait()`

### google-decisions:interfaces/real-need — Interfaces: real need, consumer-owned, small
- **meta:** severity=should · scope=decl · check=lint+llm · lint=iface~unused,interfacebloat · overlaps=google-guide:simplicity
- **rule:** Avoid creating interfaces until a real need exists; model required behavior, not
  named patterns ("service", "repository"). Do not wrap RPC clients in manual interfaces just
  for abstraction or testing, and do not export test doubles or back doors solely for tests.
  The consumer defines the interface with only the methods it uses; the producer exports one
  only if the interface is the product (a common protocol). Keep interfaces small, document
  their contract, edge cases and errors, and keep internal-only ones unexported.
- **look for:** an exported interface next to its only implementation; `XService` /
  `XRepository` interfaces mirroring a struct's methods; interfaces over generated RPC
  clients; exported fakes in non-test packages; undocumented interface contracts.
- **skip:** interfaces unused in their own package (iface unused) and ones with over 10
  methods (interfacebloat) are reported by linters; interfaces that are the product.
- **example:** exported `UserService` beside its only implementation -> consumer-side interface

### google-decisions:interfaces/return-concrete — Interfaces: accept interfaces, return concrete types
- **meta:** severity=should · scope=decl · check=lint+llm · lint=iface~opaque
- **rule:** Functions should take interfaces as arguments but return concrete types, so callers
  get every exported method and field and can still pass the result on as an interface.
  Returning an interface is acceptable for encapsulation (e.g. `error`) and for command,
  chaining, factory and strategy patterns.
- **look for:** exported functions returning an interface where the concrete type would serve
  callers better and none of the listed patterns applies.
- **skip:** a function that always returns one concrete type behind an interface — iface
  opaque reports it; `error` results; factories choosing among implementations.
- **note:** `ireturn` flags every interface return and needs allow-lists for the exceptions.
- **example:** `func NewStore() Store { return &store{} }` -> `func NewStore() *Store`

### google-decisions:generics — Generics
- **meta:** severity=should · scope=decl · check=llm · custom=generic-single-instantiation · overlaps=google-guide:least-mechanism
- **rule:** Use generics where they meet a real requirement; slices, maps and interfaces often
  work as well with less complexity, so be wary of premature use. Do not add type parameters
  just because code is element-agnostic: with one type instantiated in practice, write it for
  that type. Do not use generics to build DSLs, error-handling frameworks or assertion
  libraries. If types share a useful interface, model with it; instead of `any` plus heavy
  type switching, consider generics. Document exported generic APIs, ideally with runnable
  examples.
- **look for:** type parameters with a single instantiation; generic `Result[T]`/`Try`
  error plumbing; generic assertion helpers in tests; `any` parameters with large type
  switches; undocumented exported generic APIs.
- **skip:** generic containers or algorithms with several real instantiations.
- **example:** `type Stack[T any]` used only as `Stack[Job]` -> `type jobStack []Job`

### google-decisions:pass-values — Pass values
- **meta:** severity=should · scope=body · check=lint+llm · lint=gocritic:ptrToRefParam · custom=ptr-param-deref-only
- **rule:** Do not pass pointers as arguments just to save a few bytes: if a function reads its
  argument only as `*x`, take the value. Common cases are `*string` and pointers to interfaces
  (`*io.Reader`), whose values are fixed-size anyway. This does not apply to large structs or
  small structs that may grow; pass protocol buffer messages by pointer.
- **look for:** `*string`, `*int`, `*bool` or small-struct pointer parameters that are only
  dereferenced — never written through, nil-checked, or passed on as pointers.
- **skip:** pointers to interfaces, maps or channels — gocritic ptrToRefParam reports them;
  nil-means-absent optional parameters; out-parameters; proto messages.
- **example:** `func greet(name *string) { fmt.Println(*name) }` -> `func greet(name string)`

### google-decisions:receiver-type/must-pointer — Receiver type: when a pointer is required
- **meta:** severity=must · scope=body · check=lint+llm · lint=revive:modifies-value-receiver,staticcheck:SA4005
- **rule:** Correctness wins over speed or simplicity. A method that mutates its receiver,
  including reslicing or reassigning a slice receiver, must have a pointer receiver; so must
  methods of a struct holding fields that cannot safely be copied (`sync.Mutex` and other
  synchronization types; check the field type's godoc).
- **look for:** value receivers reassigned as a whole (`q = append(q, x)`); value receivers
  on structs with non-lock uncopyable fields such as `bytes.Buffer`.
- **skip:** field assignments through a value receiver (revive modifies-value-receiver,
  staticcheck SA4005); value receivers on structs with locks (govet copylocks); element writes
  through slice or map value receivers, which the caller sees.
- **example:** `func (c Counter) Inc() { c.n++ }` -> `func (c *Counter) Inc() { c.n++ }`

### google-decisions:receiver-type/choice — Receiver type: value or pointer
- **meta:** severity=should · scope=decl · check=lint+llm · lint=recvcheck
- **rule:** Choose by method set and intent. Values: slices the method does not reslice;
  maps, funcs and channels; built-in types that need no modification; small plain-data
  structs or arrays without mutable fields or pointers (like `time.Time`). Pointers: large
  structs or arrays; structs with pointers to data that may be mutated (to show it); when in
  doubt. Methods running concurrently with code that modifies the receiver take a value only
  if those changes must stay invisible. Prefer all-pointer or all-value methods per type, and
  do not decide on unprofiled performance beliefs.
- **look for:** pointer receivers on map, func or chan types (`func (h *Header) Add`); value
  receivers on large structs or on structs whose `*T` fields the methods mutate through.
- **skip:** mixed receiver kinds on one type — recvcheck reports them.
- **example:** `func (h *Header) Add(k, v string)` on a map type ->
  `func (h Header) Add(k, v string)`

### google-decisions:switch-break — `switch` and `break`
- **meta:** severity=should · scope=body · check=lint+llm · lint=staticcheck:S1023~break,revive:useless-break,staticcheck:SA4011
- **rule:** Do not end `switch` clauses with an unlabeled `break`: Go cases do not fall through,
  so it is redundant; mark an intentionally empty clause with a comment instead. Inside a
  `for` loop, a bare `break` in a `switch` or `select` exits only that statement; use a
  labeled `break` to leave the loop.
- **look for:** a `break` in the middle of a case (e.g. inside an `if`) within a loop where
  the code clearly means to stop the loop.
- **skip:** trailing `break` in a case (staticcheck S1023, revive useless-break) and
  ineffective trailing breaks in loops (staticcheck SA4011) — reported by linters.
- **example:** `case "C":⏎    break` -> `case "C":⏎    // handled outside of the switch`

### google-decisions:synchronous-functions — Synchronous functions
- **meta:** severity=should · scope=decl · check=llm
- **rule:** Prefer synchronous functions, which return their results directly and finish any
  callbacks or channel operations before returning, over asynchronous ones. They keep
  goroutines local to the call, so lifetimes, leaks and races are easy to reason about, and
  they are easier to test. Callers can add concurrency; removing it is hard or impossible.
- **look for:** functions that start a goroutine and return a channel, future or callback
  hook instead of the result; APIs that return before their work completes with no way to
  wait for it.
- **skip:** inherently asynchronous APIs (servers, subscriptions) whose lifetime is
  documented and controllable (ctx, `Close`/`Stop`).
- **example:** `func Fetch(url string) <-chan Result` ->
  `func Fetch(ctx context.Context, url string) (Result, error)`

### google-decisions:type-aliases — Type aliases
- **meta:** severity=should · scope=decl · check=llm
- **rule:** Use a type definition (`type T1 T2`) to define a new type, and a type alias
  (`type T1 = T2`) only to refer to an existing type without defining a new one. Aliases are
  rare, mainly a tool for migrating packages to new locations; don't alias when not needed.
- **look for:** `type X = Y` used as a local shorthand or rename, or where a distinct type
  (own methods, type safety) was intended.
- **skip:** aliases kept for compatibility while a type moves to another package or is
  deprecated.
- **example:** `type userMap = map[string]*User` as a shorthand -> the plain type, or
  `type userMap map[string]*User`

### google-decisions:use-percent-q — Use %q
- **meta:** severity=should · scope=body · check=lint+llm · lint=gocritic:sprintfQuotedString · custom=manual-quote-verb
- **rule:** Prefer the `%q` verb to quoting a string by hand with `"%s"` or `'%s'`, especially in
  output meant for humans where the value may be empty or contain control characters: a
  quoted `""` stands out where an empty string would vanish.
- **look for:** `\"%s\"`, `'%s'` or `"%v"` around values in `Printf`, `Errorf`, logger and
  `t.Errorf`-style calls.
- **skip:** `fmt.Sprintf` with `"%s"` or `` `%s` `` — gocritic sprintfQuotedString reports
  it; machine-readable output that needs a specific quoting (SQL, shell, CSV).
- **example:** `fmt.Printf("value \"%s\" looks like English text", someText)` ->
  `fmt.Printf("value %q looks like English text", someText)`

### google-decisions:use-any — Use any
- **meta:** severity=should · scope=decl · check=lint · lint=revive:use-any
- **rule:** Prefer `any` to `interface{}` in new code; since Go 1.18 `any` is an alias, so the
  two are interchangeable.
- **skip:** reported by revive use-any.
- **example:** `func Log(v interface{})` -> `func Log(v any)`
