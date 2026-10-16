# Uber Go Style Guide — Globals and Lifecycle

Uber's guidance on atomics, package-level state, embedding, built-in names, `init()`, exiting
the program, serialized structs and goroutine lifetimes.

### uber:use-gouberorgatomic — Use go.uber.org/atomic
- **meta:** severity=should · scope=body · check=lint+llm · lint=modernize:atomictypes · custom=mixed-atomic-access
- **rule:** Don't drive raw `int32`/`int64` fields with `sync/atomic` functions: it is easy to
  forget the atomic operation on some read or write, which is a data race. Use atomic types
  that hide the raw value; the guide recommends `go.uber.org/atomic`, which also offers
  `atomic.Bool`.
- **look for:** fields such as `running int32 // atomic` updated with `atomic.SwapInt32` but
  read or written plainly elsewhere (`f.running == 1`) — modernize only flags variables whose
  every use is atomic.
- **skip:** code already on typed atomics (`sync/atomic` types or `go.uber.org/atomic`).
- **example:** `running int32` with `atomic.SwapInt32(&f.running, 1)` -> `running atomic.Bool` with `f.running.Swap(true)`
- **note:** The advice predates Go 1.19, which added typed values to `sync/atomic` (`Bool`,
  `Int32`, `Int64`, `Uint32`, `Uint64`, `Uintptr`, `Pointer[T]`); point fixes at those rather
  than at the third-party module.

### uber:avoid-mutable-globals — Avoid Mutable Globals
- **meta:** severity=should · scope=repo · check=lint+llm · lint=gochecknoglobals · custom=global-mutation · overlaps=google-practices:globals
- **rule:** Avoid mutating global variables, function pointers included; opt for dependency
  injection instead (a struct field set by the constructor, a parameter), which also lets
  tests substitute dependencies without swapping globals.
- **look for:** package variables reassigned in functions or tests (save, override, deferred
  restore); function variables used as test seams (`var _timeNow = time.Now`); setters of
  package state; writes to other packages' globals.
- **skip:** package variables never reassigned after initialization — gochecknoglobals reports
  every package variable, so check for mutation.
- **example:** `var _timeNow = time.Now` -> `type signer struct{ now func() time.Time }` filled by `newSigner()`

### uber:avoid-embedding-types-in-public-structs — Avoid Embedding Types in Public Structs
- **meta:** severity=should · scope=decl · check=llm · custom=exported-struct-embedding · conflicts=effective:embedding
- **rule:** Don't embed types (structs or interfaces) in exported structs: embedding leaks
  implementation details, obscures documentation and limits evolution — adding methods to an
  embedded interface, removing methods from an embedded struct, and removing or even replacing
  the embedded type are all breaking changes. Use a named field and hand-write the delegating
  methods you mean to expose.
- **look for:** exported structs embedding a shared base implementation (`*AbstractList`) or an
  interface; embedded exported types that thereby become public fields.
- **skip:** unexported structs; test doubles in `_test.go` files; embedded mutexes (mutex rule).
- **example:** `type ConcreteList struct{ *AbstractList }` -> `type ConcreteList struct{ list *AbstractList }` plus `Add`/`Remove` delegates

### uber:avoid-using-built-in-names — Avoid Using Built-In Names
- **meta:** severity=should · scope=decl · check=lint+llm · lint=predeclared
- **rule:** Don't use predeclared identifiers (`error`, `string`, `len`, `new`, ...) as names:
  depending on context they shadow the builtin in that scope or, as field and method names,
  make code confusing and hard to grep.
- **look for:** struct fields and methods named after builtins (`error error`,
  `string string`) — predeclared checks them only with its qualified-name option.
- **skip:** variables, parameters, constants, types and functions — predeclared reports them.
- **example:** `func handleErrorMessage(error string)` -> `func handleErrorMessage(msg string)`

### uber:avoid-init/declarations — Avoid `init()`: prefer declarations
- **meta:** severity=should · scope=repo · check=lint+llm · lint=gochecknoinits · overlaps=effective:init
- **rule:** Avoid `init()` where possible: compute package values in variable initializers (or a
  helper they call, which is also testable) and move other setup into `main()` or elsewhere in
  the program's lifecycle. `init()` may be preferable or necessary for complex expressions that
  cannot be a single assignment, pluggable hooks (`database/sql` dialects, encoding
  registries) and deterministic precomputation.
- **look for:** `init()` that only assigns package variables (`_defaultFoo = Foo{...}`); setup a
  constructor or `main()` could own.
- **skip:** the preferable uses above (gochecknoinits reports every `init()`).
- **example:** `func init() { _defaultFoo = Foo{...} }` -> `var _defaultFoo = defaultFoo()`

### uber:avoid-init/side-effects — Avoid `init()`: no environment, I/O or ordering
- **meta:** severity=should · scope=body · check=llm · custom=init-side-effects · conflicts=effective:init
- **rule:** When `init()` is unavoidable, it should be completely deterministic, not depend on
  the order or side effects of other `init()` functions, not read or change global or
  environment state (machine information, environment variables, working directory, program
  arguments), and do no I/O (filesystem, network, system calls). Code that can't meet this
  belongs in `main()` or a helper it calls; libraries in particular should avoid "init magic".
- **look for:** `init()` calling `os.Getenv`, `os.Getwd`, `os.ReadFile`, `flag` or `os.Args`,
  dialing services, reading the clock or randomness, or relying on another file's `init()`.
- **skip:** registering pluggable hooks (`sql.Register`, codec registries).
- **example:** `func init() { raw, _ := os.ReadFile(...); yaml.Unmarshal(raw, &_config) }` -> `func loadConfig() Config` called from `main`

### uber:exit-in-main — Exit in Main
- **meta:** severity=should · scope=body · check=lint+llm · lint=revive:deep-exit · conflicts=google-decisions:dont-panic, google-practices:checks-and-panics
- **rule:** Call `os.Exit` or `log.Fatal*` only in `main()`; all other functions return errors
  to signal failure. Exiting elsewhere obscures control flow, makes code hard to test (it ends
  the test binary) and skips deferred cleanup. Panicking is not a way to exit either.
- **look for:** exits inside `init()` (revive allows them there); third-party fatal loggers
  (`logrus.Fatal`, zap's `Logger.Fatal`, `klog.Fatal`) and helpers that exit on behalf of their
  callers.
- **skip:** `os.Exit(m.Run())` in `TestMain`; calls revive already reports.
- **example:** `func readFile(path string) string { ...; log.Fatal(err) }` -> `func readFile(path string) (string, error)`
- **note:** revive's deep-exit also reports `log.Panic*` and `flag.Parse` outside `main`/`init`.

### uber:exit-once — Exit Once
- **meta:** severity=should · scope=body · check=lint+llm · lint=gocritic:exitAfterDefer · custom=multiple-exits-in-main
- **rule:** If possible, call `os.Exit` or `log.Fatal` at most once in `main()`: move the logic
  and its error paths into a separate function (`run() error`, or `run() int` returning the
  exit code; name and signature are free) so `main` stays short, the logic becomes testable
  and deferred calls are not skipped.
- **look for:** `main()` with several `log.Fatal`/`os.Exit` calls, or with the business logic
  inline.
- **skip:** exit calls after a `defer` in the same function — gocritic reports them.
- **example:** `main` with three `log.Fatal(err)` calls -> `func main() { if err := run(); err != nil { log.Fatal(err) } }`

### uber:use-field-tags-in-marshaled-structs — Use field tags in marshaled structs
- **meta:** severity=should · scope=body · check=lint+llm · lint=musttag
- **rule:** Annotate every field of a struct marshaled to JSON, YAML or another format with
  tag-based field naming with the relevant tag: the serialized form is a contract between
  systems, and explicit names keep a refactoring or rename from silently breaking it.
- **look for:** structs serialized through helpers musttag doesn't know (web framework
  `c.JSON`, generic encode wrappers taking `any`, other codecs); partially tagged structs.
- **skip:** types with their own marshal/unmarshal methods; generated code.
- **example:** `Price int` -> `` Price int `json:"price"` ``

### uber:dont-fire-and-forget-goroutines/lifetime — Don't fire-and-forget goroutines: controlled lifetimes
- **meta:** severity=must · scope=body · check=llm · custom=goroutine-without-stop · overlaps=google-decisions:goroutine-lifetimes
- **rule:** Don't leak goroutines in production code. Every goroutine must either stop at a
  predictable time or have a way to be signalled to stop, and in both cases code must be able
  to block until it has exited. Goroutines with unmanaged lifetimes cost memory and CPU, keep
  objects from being garbage collected and hold on to unused resources.
- **look for:** `go func() { for { ...; time.Sleep(d) } }()` with no stop channel or
  `ctx.Done()`; goroutines spawned per request or item with no cancellation; goroutines that
  can block forever on a channel nobody serves.
- **skip:** goroutines that are both signalled and awaited (stop and done channels, a context
  plus a `WaitGroup` or `errgroup`).
- **example:** `go func() { for { flush(); time.Sleep(delay) } }()` -> a `select` on `ticker.C` and `<-stop` with `defer close(done)`; shut down by `close(stop); <-done`

### uber:dont-fire-and-forget-goroutines/goleak — Don't fire-and-forget goroutines: leak tests
- **meta:** severity=consider · scope=test · check=llm
- **rule:** Test packages that may spawn goroutines for goroutine leaks with
  `go.uber.org/goleak`.
- **look for:** packages that start goroutines whose tests have neither
  `goleak.VerifyTestMain(m)` nor `defer goleak.VerifyNone(t)`.

### uber:wait-for-goroutines-to-exit — Wait for goroutines to exit
- **meta:** severity=must · scope=body · check=llm · overlaps=google-decisions:goroutine-lifetimes
- **rule:** For every goroutine the system spawns there must be a way to wait for it to exit: a
  `sync.WaitGroup` when there are several, or a `chan struct{}` that the single goroutine
  closes when it is done (`defer close(done)`).
- **look for:** `Stop`/`Close`/`Shutdown` methods that signal (`close(stop)`, `cancel()`) but
  return without waiting; `go` statements in loops with no `WaitGroup` or `errgroup`; done
  channels closed on some paths only instead of via `defer`.
- **example:** `for _, j := range jobs { go run(j) }` -> `wg.Go(func() { run(j) })` in the loop, then `wg.Wait()`
- **note:** `WaitGroup.Go` needs Go 1.25; older code pairs `wg.Add(1)` with `defer wg.Done()`.

### uber:no-goroutines-in-init — No goroutines in `init()`
- **meta:** severity=should · scope=body · check=llm · custom=go-in-init · overlaps=google-decisions:goroutine-lifetimes
- **rule:** `init()` functions should not spawn goroutines. A package that needs a background
  goroutine must expose an object that manages its lifetime: started only when the user asks
  for it (a constructor), with a method (`Close`, `Stop`, `Shutdown`) that signals the
  goroutine to stop and waits for it to exit (with a `WaitGroup` if it runs several).
- **look for:** `go` statements in `init()` or in package-level variable initializers;
  background workers that start on import with no way to stop them.
- **example:** `func init() { go doWork() }` -> `w := NewWorker(...)` whose `Shutdown()` closes `stop` and waits on `done`
