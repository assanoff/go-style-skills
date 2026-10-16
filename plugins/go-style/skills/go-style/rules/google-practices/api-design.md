# Google Go Style Best Practices — API design

API shape: function argument lists, option structs and variadic options, command-line
interfaces, package-level (global) state, and interfaces.

### google-practices:funcargs — Function argument lists
- **meta:** severity=consider · scope=decl · check=lint+llm · lint=revive:argument-limit
- **rule:** Don't let signatures grow long: with many parameters each one's role blurs,
  adjacent parameters of the same type are easy to swap, and call sites are hard to read.
  Split a highly configurable function into simpler ones (they may share an unexported
  implementation), or move inputs into an option struct or variadic options, chosen by how
  the calls look across the expected use cases. Mainly for exported APIs; use judgment.
- **look for:** runs of adjacent same-typed parameters (`a, b string, x, y bool`); bool or
  literal arguments whose meaning is invisible at the call site; one function whose flags
  select between several behaviours.
- **skip:** parameter counts over the limit, which revive reports; unexported helpers with
  few callers; signatures fixed by an interface or callback type.
- **example:** `EnableReplication(ctx, cfg, prim, ro, true, false, time.Hour, 100, w)` -> `EnableReplication(ctx, storage.ReplicationOptions{...})`

### google-practices:option-structure — Option structure
- **meta:** severity=consider · scope=decl · check=llm
- **rule:** An option struct collects some or all of a function's arguments and is passed as
  the last parameter; export it only if an exported function uses it. Field names make calls
  self-documenting and hard to swap, defaults can be omitted, each field gets its own doc,
  and the struct grows without breaking callers. It fits when all callers set some options,
  many callers set many, or several functions share the options. Contexts never go in it.
- **look for:** long parameter lists where callers mostly pass the same values; option
  structs that are not the last parameter; exported option structs used only by unexported
  functions.
- **skip:** `context.Context` fields (google-decisions:contexts, containedctx); functions with
  a few clearly distinct parameters.
- **example:** `func EnableReplication(ctx context.Context, cfg *Config, prim, ro []string, existing, overwrite bool)` -> `func EnableReplication(ctx context.Context, opts ReplicationOptions)`

### google-practices:variadic-options — Variadic options
- **meta:** severity=consider · scope=decl · check=llm
- **rule:** Variadic options (exported functions returning closures that update an
  unexported config struct) need a lot of extra code; use them only when that pays off: most
  callers need no options, options are many or rarely used, take arguments, can fail (the
  option returns an `error`), need long docs, or other packages may define their own. Apply
  options in order so the last one wins for conflicting or repeated non-cumulative options.
  Keep the option function's parameter type unexported unless third-party options are wanted.
- **look for:** an option framework for two or three settings that every caller passes;
  options applied out of order (via a map, first one wins); exported option config structs.
- **skip:** the choice between option structs and variadic options when it is close.
- **example:** `func Dial(addr string, opts ...Option)` where every caller passes `WithTimeout` -> a `timeout` parameter or an option struct

### google-practices:variadic-options/parameters — Variadic options: take values, not presence
- **meta:** severity=should · scope=decl · check=llm · custom=option-presence-flag
- **rule:** An option takes a parameter instead of signalling its value by being present:
  a binary setting takes a `bool`, an enumerated one an enum constant. With presence-only
  options, callers that pick options at run time must change which options they pass rather
  than just the arguments; don't assume every user knows the option set statically.
- **look for:** zero-argument option constructors such as `EnableFailFast()`,
  `DisableCache()` or `CapacitorFormat()`; `EnableX`/`DisableX` pairs.
- **skip:** option constructors in generated or third-party code.
- **example:** `rpc.EnableFailFast()` -> `rpc.FailFast(enable bool)`; `log.CapacitorFormat()` -> `log.Format(log.Capacitor)`

### google-practices:complex-clis — Complex command-line interfaces
- **meta:** severity=consider · scope=repo · check=llm
- **rule:** For CLIs with sub-commands, `subcommands` is the default when nothing else
  decides (simple, Go flag convention, easy to use correctly); use `cobra` (getopt flags,
  many features, some pitfalls) when you need what it adds. A package per sub-command is not
  required: apply the usual package-boundary judgement. Code usable both as a library and as
  a binary keeps the CLI separate, as just one more client of the library.
- **look for:** logic other code would want to import living in `main` or command handlers;
  one package per sub-command with no reason; CLI parsing inside library packages.
- **skip:** the choice of cobra as such; flag definitions in libraries (google-decisions:flags).
- **example:** whole implementation inside `cmd/tool/main.go` -> library package `tool` plus a thin `main`

### google-practices:complex-clis/cobra-context — Complex CLIs: cobra commands use cmd.Context()
- **meta:** severity=should · scope=body · check=llm · custom=cobra-background-context · overlaps=google-decisions:contexts
- **rule:** cobra command functions get their context from `cmd.Context()` instead of
  creating a root context with `context.Background()`. (`subcommands` already passes the
  right context as a parameter.)
- **look for:** `context.Background()`/`context.TODO()` inside `Run`/`RunE`/`PreRunE`
  functions of a `cobra.Command`, or in helpers they call without passing a context.
- **skip:** `main` creating the root context for `cmd.ExecuteContext(ctx)`.
- **example:** `RunE: func(cmd *cobra.Command, args []string) error { return run(context.Background()) }` -> `return run(cmd.Context())`

### google-practices:globals — Global state
- **meta:** severity=should · scope=repo · check=llm
- **rule:** Libraries should not force clients onto APIs that rely on package-level state,
  nor export package-level variables that control behaviour for all clients. If the
  functionality keeps state, let clients create instances (`sidecar.New()`) and pass them as
  explicit dependencies (parameters, struct fields). Global APIs break down as clients
  multiply: order-dependent tests, no parallel or sharded runs, one instance per process,
  registration collisions, init-time rules. Most critical for shared infrastructure libraries.
- **look for:** package-level `Register`/`Set`/`Use` functions over hidden state with no
  instance type behind them; exported mutable configuration variables; library code that
  only works after callers set up some global elsewhere.
- **skip:** `package main`; the variables themselves (globals-forms); state that passes
  globals-litmus-tests.
- **example:** `var registry = map[string]*Plugin{}; func Register(...)` -> `type Registry struct{...}; func New() *Registry; func (r *Registry) Register(...)`

### google-practices:globals-forms — Major forms of package state APIs
- **meta:** severity=should · scope=repo · check=lint+llm · lint=gochecknoglobals
- **rule:** Apply extreme scrutiny to these forms of package state: top-level variables
  (exported or not), a service locator held in a global, registries of callbacks and
  similar behaviours, and thick-client singletons for backends, storage, data access and
  other resources. Legacy APIs, even in the standard library, that are configured through
  globals are no precedent for new code.
- **look for:** which gochecknoglobals reports hold mutable state: `var hooks []func()` with
  an `OnX(f)` registrar, a lazily initialised `var client *C` behind `func Client() *C`;
  `init()` functions registering into another package's global registry.
- **skip:** globals that pass globals-litmus-tests (logically constant tables, private
  caches); fixtures in `_test.go` files (t-custom-main, t-setup-amortization); `package main`.
- **example:** `var unhealthyFuncs []func(); func OnUnhealthy(f func())` -> a `Health` type with an `OnUnhealthy` method

### google-practices:globals-litmus-tests — Litmus tests
- **meta:** severity=consider · scope=repo · check=llm · custom=test-global-swap
- **rule:** Package state is unsafe when otherwise independent code or test cases interact
  through it, when users are tempted to swap it for a test double, or when callers must
  respect ordering (`init`, before or after flag parsing). Free of those, it is acceptable
  only if: it is logically constant; observable behaviour is stateless (a private cache whose
  hits and misses callers cannot tell apart); it does not bleed outside the process (sidecars,
  shared files); or nobody expects predictable behaviour (`math/rand`).
- **look for:** tests that overwrite package variables or re-register implementations
  (`old := pkg.Now; pkg.Now = fake; defer ...`); tests that fail when run alone or in another
  order; APIs documented as "call only during init" or "before flag.Parse".
- **skip:** `image.RegisterFormat`-style registries of stateless, idempotent decoders.
- **example:** `sidecar.Register("cloudlogger", fakeLogger)` in a test -> pass a `*sidecar.Registry` holding the fake

### google-practices:globals-default-instance — Providing a default instance
- **meta:** severity=should · scope=repo · check=llm
- **rule:** A convenience API backed by package-level state is not recommended but
  acceptable to maximise convenience if it passes the litmus tests and: clients can create
  isolated instances of the package's types; the package-level functions are thin proxies
  to a default instance (`http.Handle` -> `http.DefaultServeMux.Handle`); it documents and
  enforces its invariants (when it may be called, whether concurrently); and it offers a way
  to reset the global state to a known-good default, for example for tests.
- **look for:** package-level functions with logic of their own instead of delegating to an
  instance; no exported instance type or constructor; undocumented lifecycle or concurrency
  rules; no reset hook.
- **skip:** libraries calling such APIs (globals-default-instance/libraries).
- **example:** `func Register(n string, p *Plugin) { registry[n] = p }` -> `func Register(n string, p *Plugin) { Default.Register(n, p) }` plus `New()` and documented rules

### google-practices:globals-default-instance/libraries — Providing a default instance: binaries only
- **meta:** severity=should · scope=body · check=llm · custom=library-default-instance
- **rule:** Only binaries use package-level default-instance APIs. Libraries, and above all
  infrastructure packages that others import, must not rely on the package-level state of
  the packages they import: they accept the instance as a dependency
  (`func Register(r *sidecar.Registry, l *Logger)`). Exception: a library in the middle of a
  refactoring towards dependency passing.
- **look for:** non-main packages calling `http.Handle`/`http.HandleFunc`, using
  `http.DefaultServeMux` or `http.DefaultClient` (also via `http.Get`), registering into
  another package's global registry, or reading another package's global configuration.
- **skip:** `package main`; test files.
- **example:** `func init() { http.HandleFunc("/debug", h) }` in a library -> `func RegisterHandlers(mux *http.ServeMux)`

### google-practices:avoid-unnecessary-interfaces — Avoid unnecessary interfaces
- **meta:** severity=should · scope=decl · check=lint+llm · lint=iface~identical methods · overlaps=google-decisions:interfaces
- **rule:** Don't create an interface before a real need: a "service" or "repository"
  concept needs no `type Service interface`; start from a concrete type. Reuse existing
  interfaces such as generated RPC clients rather than wrapping them for abstraction or
  tests (use real transports). Don't export test doubles from the API that consumes an
  interface; test through the real implementation's public API. Interfaces earn their place
  for two or more implementations under one logic, for decoupling packages (cycles often
  signal bad package structure), or when a consumer needs one or two methods of a big type.
- **look for:** interfaces with one implementation beside them; pattern-named interfaces
  (`Service`, `Repository`, `Manager`) mirroring one struct; hand-written interfaces wrapping
  a generated `XxxClient`; exported `Fake*`/`Mock*` types in production packages.
- **skip:** duplicate interfaces within a package (iface reports them); doubles in a
  dedicated `xxxtest` package; interfaces with a material need for substitution.

### google-practices:interface-ownership-and-visibility — Interface ownership and visibility
- **meta:** severity=should · scope=decl · check=lint+llm · lint=iface~declared but not used,iface~declared on interface · custom=exported-internal-interface · overlaps=google-decisions:interfaces
- **rule:** Keep an interface unexported if only the package's own logic uses it; exporting
  commits you to maintaining it for external callers. Interfaces generally belong to the
  consumer, which lists only the methods it uses. A producer exports the interface when the
  interface is the product (a protocol such as `io.Writer`, `hash.Hash` or a generated proto
  service, possibly in its own implementation-free package), to spare many packages from
  mirroring identical interfaces, or to break an import cycle.
- **look for:** an interface declared beside its only implementation and returned by its
  constructor; exported interfaces used only inside their package; consumer interfaces
  listing methods the consumer never calls.
- **skip:** packages whose purpose is the protocol; generated code.
- **example:** `package storage; type Store interface{...}; type store struct{...}` -> concrete `storage.Store`; consumers declare `type userGetter interface{ Get(...) }`

### google-practices:designing-effective-interfaces/small — Designing effective interfaces: keep them small
- **meta:** severity=consider · scope=decl · check=lint+llm · lint=interfacebloat · overlaps=google-decisions:interfaces
- **rule:** Keep interfaces small: the larger the interface, the harder it is to implement
  and to write code that takes advantage of it. Compose larger interfaces from small ones
  when needed.
- **look for:** interfaces whose callers each use a few of many methods; one interface
  mixing unrelated responsibilities that could be split and embedded.
- **skip:** interfaces over the method limit, which interfacebloat reports; generated code.
- **example:** one `Store` with `Get`, `Put`, `List`, `Watch`, `Stats`, ... used for `Get` only -> `type Getter interface{ Get(...) }`

### google-practices:designing-effective-interfaces/docs — Designing effective interfaces: documentation
- **meta:** severity=should · scope=body · check=llm · custom=undocumented-interface-method · overlaps=google-decisions:interfaces
- **rule:** Document an interface as the user manual of its abstraction, in proportion to
  its cognitive load rather than its method count. On a single-method interface the type
  comment explains the contract, edge cases and expected errors; each method of a
  multi-method interface has its own comment; unexported interfaces are worth documenting
  too, as they often glue internal logic together.
- **look for:** exported multi-method interfaces with undocumented methods; interface
  comments that restate the name without contract, edge cases or error behaviour.
- **skip:** a missing doc comment on the exported type itself (revive `exported`,
  google-decisions:doc-comments).
- **example:** `type Store interface { Get(key string) ([]byte, error) }` -> `// Get returns the value for key, or ErrNotFound if ...` above `Get`

### google-practices:designing-effective-interfaces/return-concrete — Designing effective interfaces: return concrete types
- **meta:** severity=should · scope=decl · check=lint+llm · lint=iface~single concrete implementation · overlaps=google-decisions:interfaces
- **rule:** Accept interfaces, return concrete types, so callers can use the whole value
  without being locked into one abstraction. Return an interface when it encapsulates
  something whose extra methods would let callers break integrity or would block changing
  the provider (`error` is the usual case; don't encapsulate by rote), when the function
  picks one of several concrete types at run time (factory, strategy, command, chaining
  APIs), or when returning the concrete type would create an import cycle (often a sign of
  badly split packages).
- **look for:** which iface reports lack an encapsulation or cycle reason; interfaces declared
  only so that `New` can return them.
- **skip:** `error` results; factories returning different types per branch.
- **example:** `func NewStore() Store { return &store{} }` -> `func NewStore() *Store`
