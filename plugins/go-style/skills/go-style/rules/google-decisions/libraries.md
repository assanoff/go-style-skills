# Google Style Decisions — Common libraries

Decisions on flags, logging, `context.Context` and `crypto/rand`; advice written for Google-internal libraries (its flag package, its glog-style `log`) is generalized only where the principle holds outside Google, as each `note` says.

### google-decisions:flags/naming — Flags: names and declarations
- **meta:** severity=should · scope=body · check=llm · custom=flag-name-style
- **rule:** Flag names use snake_case (`poll_interval`), while the variables holding their values
  use Go mixedCaps (`pollInterval`). Global flag variables go in their own `var` group right
  after the imports.
- **look for:** camelCase flag names (`flag.Int("pollIntervalSeconds", ...)`); flag variables
  scattered among other globals or declared far from the imports.
- **skip:** underscores in the Go variable name — revive var-naming reports them
  (google-guide:mixed-caps); projects with an established kebab-case flag style (common with
  `pflag`/cobra).
- **note:** snake_case flag names are a Google convention tied to its internal flag package;
  outside Google follow the project's CLI style. The variable-naming half applies everywhere.
- **example:** `poll_interval = flag.Int("pollIntervalSeconds", 60, "...")` ->
  `pollInterval = flag.Int("poll_interval_seconds", 60, "...")`

### google-decisions:flags/main-only — Flags: only in package main
- **meta:** severity=must · scope=repo · check=llm · custom=flag-outside-main
- **rule:** Define flags only in `package main` or equivalent. General-purpose packages are
  configured through Go APIs (function arguments, struct fields, and only rarely and under
  strict scrutiny exported globals); importing a library must not register flags as a side
  effect. In the extremely rare justified exception, the flag name must clearly indicate the
  package it configures.
- **look for:** `flag.String`/`Int`/`Bool`/`Duration`/`Var` (or `pflag`) registrations at
  package level or in `init` of non-main packages; libraries reading global flag values.
- **skip:** local `flag.NewFlagSet` use; a CLI package that is the binary's entry point in all
  but name; test-binary flags in `_test.go` (e.g. `-update` for golden files).
- **note:** applies outside Google as written (cf. Abseil TotW #45, "avoid flags, especially
  in library code").

### google-decisions:logging — Logging
- **meta:** severity=consider · scope=body · check=lint+llm · lint=revive:unnecessary-format~\blog\. · custom=printf-single-verb
- **rule:** When there is nothing to format, call the non-formatting logging function:
  `log.Info(v)` is equivalent to `log.Infof("%v", v)`, and likewise for the other levels.
- **look for:** formatting log calls whose format is a single bare verb (`log.Infof("%v", v)`,
  `log.Printf("%s", msg)`) in any logger with paired `X`/`Xf` functions (glog, klog, std `log`).
- **skip:** std `log.*f` calls with no verbs at all — revive unnecessary-format reports them;
  `log/slog`, which has no formatting variants.
- **note:** the rest of the section describes Google's glog-like `log` (`log.Fatal` aborts
  with a stack trace, `log.Exit` without one, no `log.Panic`); std `log.Fatal` exits without a
  stack trace and std `log.Panic` exists. Don't apply glog semantics to other loggers.
- **example:** `log.Infof("%v", req)` -> `log.Info(req)`

### google-decisions:contexts/first-param — Contexts: first parameter
- **meta:** severity=must · scope=decl · check=lint · lint=revive:context-as-argument
- **rule:** A `context.Context` passed to a function or method is always its first parameter,
  in test helpers too (`readTestFile(ctx, t, path)`). Functions that get their context
  elsewhere take none: HTTP handlers (`req.Context()`), streaming RPC methods (the stream's
  `Context()`), and tests (`t.Context()`).
- **skip:** reported by revive context-as-argument (leave `allowTypesBefore` unset so that
  `t *testing.T` before `ctx` is flagged too).
- **example:** `func F(name string, ctx context.Context)` ->
  `func F(ctx context.Context, name string)`

### google-decisions:contexts/background — Contexts: take the caller's context
- **meta:** severity=should · scope=body · check=lint+llm · lint=contextcheck,noctx · custom=background-in-library
- **rule:** Pass contexts explicitly along the whole call chain, from incoming requests to
  outgoing calls. Create a base context with `context.Background()` only in entrypoints
  (`main` in binaries, `init` in libraries); code in the middle of a call chain takes its
  caller's context, and library code does not create `Background()` contexts unless it
  implements a server framework. Work that must outlive the parent's cancellation uses
  context detachment, not a fresh context. One context may be shared by several calls.
- **look for:** `context.Background()`/`TODO()` in library functions without a `ctx`
  parameter that do I/O; background work on a fresh context where detachment was meant.
- **skip:** a received ctx replaced by a new one (contextcheck) and context-less std calls
  such as `http.Get` (noctx) — reported by linters; server frameworks' per-request contexts.
- **note:** the guide points to golang/go#40221 for detachment outside Google; since Go 1.21
  use `context.WithoutCancel(ctx)`.

### google-decisions:contexts/no-struct-field — Contexts: not stored in structs
- **meta:** severity=should · scope=decl · check=lint · lint=containedctx
- **rule:** Do not add a context member to a struct type; give each method that needs one a
  `ctx` parameter. The one exception is a method whose signature must match an interface in
  the standard library or a third-party library outside your control: very rare, and at
  Google subject to review by the Go style list.
- **skip:** reported by containedctx; the interface-signature exception above.
- **example:** `type worker struct { ctx context.Context }` ->
  `func (w *worker) Run(ctx context.Context) error`

### google-decisions:contexts/tests — Contexts in tests
- **meta:** severity=should · scope=test · check=lint+llm · lint=usetesting~context\.(Background|TODO)
- **rule:** In tests, take the initial context from `(testing.TB).Context()` (Go 1.24+) rather
  than `context.Background()`; helpers, test-double setup and other functions called from the
  test body that need a context get it passed explicitly as a parameter.
- **look for:** helpers that obtain their own context (calling `t.Context()` internally)
  instead of accepting `ctx`.
- **skip:** `context.Background()`/`TODO()` in tests and helpers with a `testing.TB` in scope
  — usetesting reports them; modules targeting Go older than 1.24.
- **example:** `ctx := context.Background()` in `TestFoo` -> `ctx := t.Context()`

### google-decisions:custom-contexts — Custom contexts
- **meta:** severity=must · scope=decl · check=llm · custom=custom-context-type
- **rule:** Do not create custom context types or use interfaces other than `context.Context`
  in function signatures; there are no exceptions. Otherwise every call between packages
  needs context conversions, and automated refactorings that add context parameters become
  nearly impossible. Pass application data as parameters, in the receiver, in globals, or as
  a `context.Context` value if it truly belongs there.
- **look for:** `type Context interface { context.Context; ... }`, structs embedding
  `context.Context`, or app-specific `*AppContext`/`RequestContext` types taken as parameters
  in place of `ctx context.Context`.
- **skip:** handler signatures dictated by a third-party framework (e.g. `*gin.Context`);
  your own functions called from them should take `context.Context`.
- **example:** `func Load(c *AppContext, id string)` -> `func Load(ctx context.Context, id string)`

### google-decisions:crypto-rand — crypto/rand
- **meta:** severity=must · scope=body · check=llm
- **rule:** Do not use `math/rand` (or `math/rand/v2`) to generate keys, not even throwaway
  ones: unseeded it is completely predictable, and seeded from the clock it has only a few
  bits of entropy. Use `crypto/rand`; if text is needed, encode the bytes as hex or base64.
- **look for:** `math/rand` values that end up in keys, tokens, session IDs, nonces, salts or
  passwords; such values derived from timestamps, counters, PIDs or hashes of predictable
  data; random bytes turned into text with `string(buf)` instead of hex/base64.
- **skip:** `math/rand` for non-security uses (jitter, sampling, shuffling, test data), which
  the guide does not cover. (gosec G404 flags every `math/rand` call regardless of use, so it
  is not enabled.)
- **note:** the "unseeded" reason is dated (`math/rand` is auto-seeded since Go 1.20), but the
  package is still documented as unfit for security work; Go 1.24 added `crypto/rand.Text()`.
- **example:** `key := fmt.Sprint(rand.Int63())` (math/rand) -> `key := rand.Text()` (crypto/rand)
