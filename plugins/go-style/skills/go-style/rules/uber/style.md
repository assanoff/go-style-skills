# Uber Go Style Guide — Style

The Style section of the Uber guide covers line length and consistency, declaration
grouping and ordering, naming and imports, control flow, variable scope, and how to
initialize structs, slices, maps and format strings.

### uber:avoid-overly-long-lines — Avoid overly long lines
- **meta:** severity=consider · scope=body · check=lint · lint=lll · conflicts=google-guide:line-length,google-decisions:func-formatting,google-decisions:conditional-formatting
- **rule:** Avoid lines that make readers scroll horizontally. Uber recommends a soft limit
  of 99 characters: aim to wrap before it, but it is not a hard limit and code may
  exceed it.
- **skip:** long string literals, URLs and struct tags where a break hurts readability;
  generated code.
- **note:** Google sets no line limit and prefers refactoring to wrapping; in multi-guide
  runs Google wins and this rule is not reported. The shared config counts a tab as four columns.

### uber:be-consistent — Be Consistent
- **meta:** severity=should · scope=repo · check=llm · overlaps=google-guide:consistency,google-guide:local-consistency
- **rule:** Above all, be consistent: disparate or conflicting styles in one codebase add
  maintenance overhead, uncertainty and review friction, and lead to bugs. Apply
  guideline changes at package level or larger rather than to part of a package.
- **look for:** new code that solves a problem differently from the rest of its package
  (`make(map…)` here, `map…{}` there; a second error-wrapping, logging or options style);
  a new convention adopted in only some files of a package.
- **skip:** inconsistencies the change does not touch; code that follows the package's
  established convention even where it differs from this guide (migrate whole packages).

### uber:group-similar-declarations — Group Similar Declarations
- **meta:** severity=should · scope=decl · check=llm · custom=group-adjacent-decls
- **rule:** Group related `import`, `const`, `var` and `type` declarations into one
  parenthesized block instead of repeating the keyword (groups work inside functions
  too). Group only related declarations; keep unrelated ones apart.
- **look for:** consecutive `const x = …`, `var x = …` or `type X …` declarations that
  belong together; an unrelated constant inside an `iota` enum block
  (`EnvVar = "MY_ENV"` next to `Add`, `Subtract`).
- **skip:** repeated `import` declarations — goimports reports them (mapped to
  uber:import-group-ordering); standalone declarations with no related neighbour.
- **example:** `const a = 1` / `const b = 2` -> `const (a = 1; b = 2)`

### uber:group-similar-declarations/local — Group adjacent variable declarations
- **meta:** severity=should · scope=body · check=llm · conflicts=google-practices:vardeclinitialization
- **rule:** Exception to "group only related declarations": variables declared next to
  each other, especially inside functions, should share one `var (…)` block even if
  they are unrelated.
- **look for:** a run of adjacent declarations, typically at the start of a function,
  that mixes `x := …` with `var err error` and could be a single `var (…)` block.
- **skip:** isolated declarations; declarations separated by other statements.
- **note:** this pulls against uber:local-variable-declarations (`:=` for explicit values)
  and Google's preference for `:=`; report only clear adjacent runs.
- **example:** `caller := c.name` / `format := "json"` / `var err error` -> `var (caller = c.name; format = "json"; err error)`

### uber:import-group-ordering — Import Group Ordering
- **meta:** severity=should · scope=decl · check=lint+llm · lint=goimports · custom=import-two-groups · overlaps=google-decisions:import-grouping
- **rule:** Use two import groups separated by a blank line: the standard library first,
  then everything else (the grouping goimports applies by default).
- **look for:** std imports in a later group; the non-std group placed before the std
  group; extra groups beyond these two (own-module packages, blank imports).
- **skip:** std and non-std imports mixed in one block, unsorted imports, repeated
  `import` declarations — goimports reports them.
- **note:** goimports misses std imports split across groups and reversed groups, and
  its "File is not properly formatted" also covers plain gofmt problems. Google adds
  protobuf and side-effect groups; in multi-guide runs follow Google.
- **example:** `"fmt"`, `"os"`, `"go.uber.org/atomic"` in one group -> `"fmt"`, `"os"`, blank line, `"go.uber.org/atomic"`

### uber:package-names — Package Names
- **meta:** severity=should · scope=repo · check=lint+llm · lint=revive:package-naming~(underscore|MixedCaps|root level),revive:package-naming~bad package name,revive:package-naming~conflicts with · overlaps=google-decisions:package-names,google-practices:util-packages,effective:package-names
- **rule:** Package names are all lower-case with no capitals or underscores, short and
  succinct (callers spell them at every call site), singular (`net/url`, not
  `net/urls`), need no import alias at most call sites, and avoid uninformative names
  such as `common`, `util`, `shared` or `lib`.
- **look for:** plural names (`urls`, `handlers`, `users`); `lib`; long or compound names;
  packages that callers routinely import under an alias.
- **skip:** underscores, MixedCaps, `util`/`common`/`shared` and names that collide with a
  std package — revive reports them; `_test` package suffixes.

### uber:function-names — Function Names
- **meta:** severity=should · scope=decl · check=lint · lint=revive:var-naming~underscores in Go names; (func|method) \S+ should · overlaps=google-guide:mixed-caps,google-decisions:underscores,effective:mixed-caps
- **rule:** Function and method names use MixedCaps, following the Go community
  convention. Exception: test functions may contain underscores to group related cases
  (`TestMyFunction_WhatIsBeingTested`).
- **skip:** `Test…`, `Benchmark…`, `Example…` and `Fuzz…` functions in `_test.go` files —
  revive ignores them.
- **example:** `func parse_header()` -> `func parseHeader()`

### uber:import-aliasing — Import Aliasing
- **meta:** severity=must · scope=decl · check=llm · custom=import-alias-necessity · overlaps=google-decisions:import-renaming
- **rule:** An import must be aliased when the package name does not match the last
  element of its import path (`client "example.com/client-go"`,
  `trace "example.com/trace/v2"`).
- **look for:** unaliased imports whose path ends in `-go`, `go-…`, `.vN` or `/vN`, or
  whose identifier used in the file differs from the path's last element.
- **skip:** paths whose last element equals the package name, including std packages.
- **note:** Google mandates renames only for collisions and generated protos; in
  multi-guide runs follow google-decisions:import-renaming.

### uber:import-aliasing/avoid — Avoid unneeded import aliases
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:redundant-import-alias · custom=import-alias-necessity · overlaps=google-decisions:import-renaming
- **rule:** Apart from that case, avoid import aliases unless two imports directly
  conflict, and then rename only what resolves the conflict.
- **look for:** aliases on imports that collide with nothing
  (`runtimetrace "runtime/trace"` with no other `trace` import); both sides of a
  conflict aliased.
- **skip:** an alias equal to the path's last element — revive reports it; aliases
  required by uber:import-aliasing.
- **example:** `runtimetrace "runtime/trace"`, `nettrace "golang.net/x/trace"` -> `"runtime/trace"`, `nettrace "golang.net/x/trace"`

### uber:function-grouping-and-ordering — Function Grouping and Ordering
- **meta:** severity=should · scope=decl · check=lint+llm · lint=gocritic:typeDefFirst,funcorder · custom=receiver-grouping
- **rule:** Sort functions in rough call order and group them by receiver: `type`,
  `const` and `var` declarations first, then exported functions; a `newXYZ()`/`NewXYZ()`
  constructor right after its type and before its methods; plain utility functions
  towards the end of the file.
- **look for:** a type's methods interleaved with other types' methods or helpers;
  utility functions above the methods that call them; an unexported `newXYZ()` placed
  after the methods; `const`/`var` blocks between functions.
- **skip:** methods declared before their type, an exported `New…` constructor after the
  methods, unexported methods before exported ones — gocritic and funcorder report them.
- **example:** `Cost()` method, then `type something`, then `newSomething()` -> type, `newSomething`, methods, `calcCost`

### uber:reduce-nesting — Reduce Nesting
- **meta:** severity=should · scope=body · check=lint+llm · lint=revive:early-return,revive:indent-error-flow,revive:superfluous-else,gocritic:nestingReduce,nestif · overlaps=google-decisions:indent-error-flow,effective:if
- **rule:** Handle error cases and special conditions first, returning early or
  continuing the loop, so less code is nested several levels deep.
- **look for:** loop bodies shaped `if valid { …main path… } else { log… }` where the
  invalid case could `continue` first; the main path inside `if err == nil { … }`; main
  logic three or more levels deep that early exits would flatten.
- **skip:** else after `return`/`continue`/`break`, `if c { … } else { return }`, loops
  whose whole body is one `if`, and deeply nested `if` chains — the linters report them.
- **note:** when this conflicts with uber:reduce-scope-of-variables, reducing nesting wins.
- **example:** `if err := v.Call(); err == nil { v.Send() } else { return err }` -> `if err := v.Call(); err != nil { return err }` then `v.Send()`

### uber:unnecessary-else — Unnecessary Else
- **meta:** severity=consider · scope=body · check=lint+llm · lint=revive:unnecessary-if~by: (?!return\b) · custom=if-else-assign
- **rule:** When both branches of an `if`/`else` only set the same variable, initialize
  it to the default value and override it in a single `if`.
- **look for:** `var a T` followed by `if c { a = x } else { a = y }` with simple values.
- **skip:** `if c { v = true } else { v = false }` — revive reports it (`v = c`); branches
  with side effects, expensive values or several statements; `else if` chains;
  else-after-return, which belongs to uber:reduce-nesting.
- **example:** `var a int; if b { a = 100 } else { a = 10 }` -> `a := 10; if b { a = 100 }`

### uber:top-level-variable-declarations — Top-level Variable Declarations
- **meta:** severity=should · scope=decl · check=lint · lint=revive:var-declaration
- **rule:** At the top level use the standard `var` keyword and omit the type unless it
  differs from the expression's type (`var _e error = F()` where `F` returns a concrete
  `myError`).
- **skip:** declared types that differ from the expression's (interfaces, a non-default
  type for an untyped constant) and `var _ I = (*T)(nil)` checks — revive ignores them.
- **note:** revive also reports redundant zero-value initializers (`var n int = 0`) and
  the same redundancy in local `var` declarations; those findings map here as well.
- **example:** `var _s string = F()` -> `var _s = F()`

### uber:prefix-unexported-globals-with-_ — Prefix Unexported Globals with _
- **meta:** severity=should · scope=decl · check=llm · custom=global-underscore-prefix · conflicts=google-decisions:underscores
- **rule:** Prefix unexported top-level `var`s and `const`s with `_` so every use shows it
  is a global: package scope makes generic names easy to shadow or misuse from another
  file without a compile error. Exception: unexported error values use the `err` prefix
  without an underscore.
- **look for:** unexported package-level `var`/`const` names without `_` (`defaultPort`,
  `maxRetries`), especially generic names a local in another file could shadow.
- **skip:** `errNotFound`-style error values; exported names; the blank identifier
  (`var _ I = (*T)(nil)`); constants declared inside functions.
- **note:** revive's var-naming ignores a leading underscore, so no linter reports either
  form. Google forbids underscores in names; in multi-guide runs this rule is not reported.
- **example:** `const defaultPort = 8080` -> `const _defaultPort = 8080`

### uber:embedding-in-structs — Embedding in Structs
- **meta:** severity=should · scope=decl · check=lint · lint=embeddedstructfieldcheck~^(?!.*Mutex)
- **rule:** Embedded types should be at the top of a struct's field list, and an empty
  line must separate them from regular fields.
- **skip:** embedded mutexes — reported under uber:zero-value-mutexes-are-valid.
- **example:** `type Client struct { version int; http.Client }` -> `type Client struct { http.Client` + empty line + `version int }`

### uber:embedding-in-structs/purpose — Embed only for a tangible benefit
- **meta:** severity=should · scope=decl · check=llm
- **rule:** Embed only to add or augment functionality in a semantically appropriate way
  with no adverse effect for users. Do not embed for cosmetics or convenience, or when it
  makes the outer type harder to build or use, breaks its useful zero value or copy
  semantics, exposes unrelated, unexported or internal members, or changes its API or
  behavior. Litmus test: would all exported inner methods and fields belong directly on
  the outer type? If only some or none, use a named field.
- **look for:** embedded `sync.WaitGroup`, `bytes.Buffer` or `url.URL` that only saves
  typing; embedded interface or pointer types that make the zero value panic
  (`io.ReadWriter`); embedding that lets callers drive internals (`Lock`, `Reset`).
- **skip:** decorators that embed to override methods on purpose (a counting
  `io.WriteCloser`); embedded mutexes and embedding in exported structs — see
  uber:zero-value-mutexes-are-valid and uber:avoid-embedding-types-in-public-structs.

### uber:local-variable-declarations — Local Variable Declarations
- **meta:** severity=should · scope=body · check=llm · custom=local-var-init · overlaps=google-practices:vardeclinitialization,google-practices:vardeclzero,google-decisions:nil-slices
- **rule:** Use short variable declarations (`:=`) when setting a variable to an explicit
  value; use `var` where the default value is clearer, e.g. an empty slice that is
  appended to later.
- **look for:** `var s = "foo"` or `var n = len(xs)` inside function bodies.
- **skip:** grouped `var (…)` blocks (uber:group-similar-declarations/local); redundant
  types and empty-slice literals — revive reports them (uber:top-level-variable-declarations,
  uber:nil-is-a-valid-slice).
- **example:** `var s = "foo"` -> `s := "foo"`; `filtered := []int{}` -> `var filtered []int`

### uber:nil-is-a-valid-slice — nil is a valid slice
- **meta:** severity=should · scope=body · check=lint · lint=revive:enforce-slice-style · overlaps=google-decisions:nil-slices
- **rule:** `nil` is a valid slice of length 0: return `nil` instead of an explicit empty
  slice, and declare slices with `var s []T` (usable by `append` at once) instead of
  `[]T{}` or `make([]T, 0)`.
- **skip:** places where nil and empty slices behave differently (JSON encodes nil as
  `null`; APIs or tests that tell them apart); `make([]T, 0, n)` with a capacity.
- **example:** `if x == "" { return []int{} }` -> `if x == "" { return nil }`

### uber:nil-is-a-valid-slice/empty-check — Check slice emptiness with len
- **meta:** severity=should · scope=body · check=lint+llm · lint=staticcheck:S1009 · custom=slice-nil-compare · overlaps=google-decisions:nil-slices
- **rule:** To check whether a slice is empty, always use `len(s) == 0`; do not compare it
  with `nil`, because an allocated empty slice is not nil.
- **look for:** `s == nil` / `s != nil` used as an emptiness test (`return s == nil`,
  `if items != nil { … }` guarding processing).
- **skip:** redundant `s != nil && len(s) > 0` — staticcheck reports it; nil comparisons
  that deliberately distinguish nil from empty (e.g. before serialization).
- **example:** `return s == nil` -> `return len(s) == 0`

### uber:reduce-scope-of-variables — Reduce Scope of Variables
- **meta:** severity=should · scope=body · check=llm · custom=if-init-scope
- **rule:** Where possible keep variables in the narrowest scope, e.g. declare a value
  used only by an `if` in its init statement. Do not narrow the scope when the result is
  needed after the `if`, or when that conflicts with uber:reduce-nesting.
- **look for:** `err := f()` directly followed by `if err != nil { return err }` with
  `err` unused afterwards; variables declared well above the only block that uses them.
- **skip:** results used after the `if` (`data, err := os.ReadFile(name)`); an if-init
  that would force an `else`; init statements too long for one line.
- **example:** `err := os.WriteFile(name, data, 0644)` + `if err != nil {…}` -> `if err := os.WriteFile(name, data, 0644); err != nil {…}`

### uber:reduce-scope-of-variables/constants — Keep single-use constants local
- **meta:** severity=consider · scope=decl · check=llm · custom=single-use-global-const
- **rule:** Constants need not be package-level unless they are used in several
  functions or files or are part of the package's external contract; otherwise declare
  them inside the function that uses them.
- **look for:** unexported package-level constants referenced from a single function.
- **skip:** exported constants; constants used by several functions, files or tests;
  values that are part of the package's contract.
- **example:** `const _defaultPort = 8080` used only in `Bar` -> `const defaultPort = 8080` inside `Bar`

### uber:avoid-naked-parameters — Avoid Naked Parameters
- **meta:** severity=should · scope=body · check=llm · custom=naked-literal-arg · conflicts=google-decisions:func-formatting
- **rule:** Naked arguments hurt readability: when a parameter's meaning is not obvious,
  add a C-style comment with its name. Better yet, replace naked `bool` parameters with
  custom types, which read better, are type-safe and allow more than two states later.
- **look for:** calls passing several bare `true`/`false`/`nil` or magic numbers to
  multi-parameter functions (`printInfo("foo", true, true)`); new functions with two or
  more `bool` parameters.
- **skip:** arguments whose meaning the function name makes obvious (`SetEnabled(true)`);
  arguments that already carry a comment.
- **note:** Google advises against inline argument comments; in multi-guide runs this
  rule is not reported.
- **example:** `printInfo("foo", true, true)` -> `printInfo("foo", true /* isLocal */, true /* done */)`

### uber:use-raw-string-literals-to-avoid-escaping — Use Raw String Literals to Avoid Escaping
- **meta:** severity=should · scope=body · check=lint+llm · lint=staticcheck:S1007 · custom=escaped-quotes-literal · overlaps=google-practices:string-constants
- **rule:** Use raw string literals (backquoted; they may span lines and contain quotes)
  instead of hand-escaped strings, which are much harder to read.
- **look for:** interpreted literals with several `\"` or `\\` escapes (JSON, SQL,
  Windows paths, expected error text); multi-line text assembled from `"…\n"` pieces.
- **skip:** regexp patterns with doubled backslashes — staticcheck reports them; strings
  needing characters a raw literal cannot hold (backquotes, control characters).
- **example:** `wantError := "unknown name:\"test\""` -> `` wantError := `unknown name:"test"` ``

### uber:use-field-names-to-initialize-structs — Use Field Names to Initialize Structs
- **meta:** severity=should · scope=body · check=lint+llm · lint=govet:composites · custom=unkeyed-local-literal · overlaps=google-decisions:literal-field-names
- **rule:** Almost always specify field names in struct literals. Exception: test-table
  rows may omit them when the struct has 3 or fewer fields.
- **look for:** positional literals of struct types from the same package
  (`User{"John", "Doe", true}`), which go vet does not report.
- **skip:** unkeyed literals of other packages' types — govet reports them; test tables
  with at most 3 fields.
- **note:** Google makes field names optional for package-local types; in multi-guide
  runs follow google-decisions:literal-field-names.
- **example:** `User{"John", "Doe", true}` -> `User{FirstName: "John", LastName: "Doe", Admin: true}`

### uber:omit-zero-value-fields-in-structs — Omit Zero Value Fields in Structs
- **meta:** severity=should · scope=body · check=llm · custom=explicit-zero-field · overlaps=google-decisions:literal-zero-value-fields
- **rule:** In keyed struct literals omit fields set to their zero value unless the field
  name adds meaningful context; this cuts noise so only meaningful values are spelled out.
- **look for:** `MiddleName: ""`, `Admin: false`, `Count: 0`, `Logger: nil` in literals.
- **skip:** test-table rows, where named zero values document the case
  (`{give: "0", want: 0}`); zero values that carry meaning where they are set.
- **example:** `User{FirstName: "John", MiddleName: "", Admin: false}` -> `User{FirstName: "John"}`

### uber:use-var-for-zero-value-structs — Use var for Zero Value Structs
- **meta:** severity=should · scope=body · check=llm · custom=empty-struct-literal-decl · overlaps=google-practices:vardeclzero,google-practices:vardeclcomposite
- **rule:** When all fields are omitted, declare the struct with `var` rather than an
  empty literal; this separates zero-valued structs from initialized ones, as `make`
  does for maps and `var` for empty slices.
- **look for:** `x := T{}` or `var x = T{}` with a struct type `T`.
- **skip:** `&T{}` (see uber:initializing-struct-references); empty literals passed as
  arguments, returned, or stored in fields.
- **example:** `user := User{}` -> `var user User`

### uber:initializing-struct-references — Initializing Struct References
- **meta:** severity=should · scope=body · check=llm · custom=new-struct · overlaps=effective:composite_literals · conflicts=google-practices:vardeclcomposite,google-practices:vardeclzero
- **rule:** Create struct pointers with `&T{}` (plus fields as needed) instead of
  `new(T)`, consistent with how struct values are initialized.
- **look for:** `new(T)` with a struct type, especially followed by field assignments
  (`p := new(T); p.Name = "bar"`).
- **skip:** `new` of non-struct types (`new(int)`, `new(string)`).
- **note:** Google treats `new(T)` and `&T{}` as equally fine for zero values; in
  multi-guide runs this rule is not reported.
- **example:** `sptr := new(T); sptr.Name = "bar"` -> `sptr := &T{Name: "bar"}`

### uber:initializing-maps — Initializing Maps
- **meta:** severity=should · scope=body · check=lint+llm · lint=revive:enforce-map-style · custom=make-then-fixed-assign · overlaps=google-practices:vardeclcomposite
- **rule:** Use `make(…)` for empty maps and maps populated programmatically (it looks
  different from a nil-map declaration and makes a later size hint easy); use a map
  literal when the map holds a fixed set of elements known at initialization.
- **look for:** `m := make(map[K]V)` followed only by assignments with constant keys
  (`m[k1] = v1; m[k2] = v2`).
- **skip:** empty `map[K]V{}` literals — revive reports them; missing capacity hints —
  see uber:specifying-map-capacity-hints.
- **example:** `m := make(map[T1]T2, 3); m[k1] = v1; m[k2] = v2` -> `m := map[T1]T2{k1: v1, k2: v2}`

### uber:format-strings-outside-printf — Format Strings outside Printf
- **meta:** severity=should · scope=body · check=lint+llm · lint=govet:printf~non-constant format · custom=const-format-string
- **rule:** A format string for a `Printf`-style call that is declared outside the call's
  string literal should be a `const`, so `go vet` can check it against the arguments.
- **look for:** `msg := "…%v…"` or a package-level `var` format that is later passed with
  arguments to `fmt.Printf`, `fmt.Errorf`, `log.Printf` or a printf wrapper.
- **skip:** a non-constant format with no further arguments — govet reports it; formats
  chosen at run time (localization, user-supplied templates).
- **example:** `msg := "unexpected values %v, %v\n"` -> `const msg = "unexpected values %v, %v\n"`

### uber:naming-printf-style-functions — Naming Printf-style Functions
- **meta:** severity=should · scope=decl · check=lint+llm · lint=goprintffuncname · custom=printf-func-suffix
- **rule:** Make `Printf`-style functions recognizable to `go vet`: use a predefined name
  (`Printf`, `Errorf`, …) when possible, otherwise end the name with `f` (`Wrapf`, not
  `Wrap`); vet's option for checking extra names only accepts names ending in `f`.
- **look for:** functions or methods taking `(format string, args ...any)` that return a
  value and do not end in `f` (`func Wrap(format string, args ...any) error`).
- **skip:** printf-like functions without results — goprintffuncname reports them.
- **note:** current go vet already infers wrappers that forward to `fmt`, whatever their
  name (checked with Go 1.27); the suffix still signals the contract to readers.
