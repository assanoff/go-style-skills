# Google Go Style Best Practices — Naming

How to apply the naming guidance to function and method names, test double packages and types,
shadowing, and uninformative package names.

### google-practices:function-name-repetition — Avoid repetition in function and method names
- **meta:** severity=consider · scope=decl · check=lint+llm · lint=revive:exported~(stutters|is repetitive) · custom=name-repeats-context · overlaps=google-decisions:repetitive-with-package, google-decisions:repetitive-in-context
- **rule:** Choose names for how they read at the call site. Usually omit the types of inputs and
  outputs (when there is no collision), the receiver type and pointer-ness; do not repeat the
  package name (functions), the receiver name (methods), parameter names, or the names and types
  of results. Extra words are acceptable when needed to disambiguate similar functions.
- **look for:** package or domain words inside function names (`yamlconfig.ParseYAMLConfig`);
  the receiver type in method names (`(c *Config) WriteConfigTo`); names spelling out parameters
  or results (`OverrideFirstWithSecond(dest, source)`, `TransformToJSON(...) *jsonconfig.Config`).
- **skip:** exported names that start with the package name — revive reports them;
  disambiguating pairs (`WriteTextTo`/`WriteBinaryTo`); type-suffixed variants (`ParseInt64`).
- **example:** `func (c *Config) WriteConfigTo(w io.Writer)` -> `func (c *Config) WriteTo(w io.Writer)`

### google-practices:function-name-conventions — Noun, verb and type-suffix naming conventions
- **meta:** severity=consider · scope=decl · check=llm
- **rule:** Functions that return something get noun-like names (`JobName`); functions that do
  something get verb-like names (`WriteDetail`). Functions identical except for the types involved
  end with the type name (`ParseInt`, `ParseInt64`, `AppendInt64`); a clear "primary" variant may
  omit it (`Marshal` next to `MarshalText`).
- **look for:** side-effecting functions with noun names (`func (s *Store) Removal(id string)`);
  plain accessors with verb names (`ReturnTimeout()`); type variants that do not end with the type
  (`Int64Parse`, `ParseForInt64`) or omit it although no variant is primary.
- **skip:** functions that do work and also return results (`Parse`, `Split`, `ReadFile`) — verb
  names are right; `New...` constructors; the `Get` prefix (next rule).
- **example:** `func IntAppend(buf []byte, v int) []byte` -> `func AppendInt(buf []byte, v int) []byte`

### google-practices:function-name-conventions/get-prefix — Avoid the Get prefix
- **meta:** severity=should · scope=decl · check=llm · custom=getter-prefix · overlaps=google-decisions:getters
- **rule:** As a corollary of noun-like names for functions that return something, function and
  method names avoid the `Get` prefix: `JobName(key)`, not `GetJobName(key)`.
- **look for:** funcs and methods named `Get<Noun>`/`get<Noun>` that return a value.
- **skip:** "get" as the domain concept (HTTP GET); methods required by an interface the package
  does not own; generated code such as protobuf getters.
- **example:** `func (c *Config) GetJobName(key string) (string, bool)` -> `func (c *Config) JobName(key string) (string, bool)`

### google-practices:naming-doubles-helper-package — Name test helper packages pkg+test
- **meta:** severity=consider · scope=repo · check=llm
- **rule:** A package of test doubles or helpers for production package `foo` is safely named by
  appending `test` to the original name: `creditcard` -> `creditcardtest`.
- **look for:** non-`_test` packages holding the doubles of one production package under generic
  or differently shaped names (`mocks`, `fakes`, `testutil`, `testhelpers`, `creditcardmocks`).
- **skip:** generated mock packages; helper packages serving many production packages, which have
  no single base name to extend.
- **example:** `package creditcardmocks` -> `package creditcardtest`

### google-practices:naming-doubles-simple — Concise double names for a single type
- **meta:** severity=consider · scope=decl · check=llm
- **rule:** When a helper package doubles only one type, give the double a concise name such as
  `Stub`: the package name and domain types already say what `creditcardtest.Stub` stands for, so
  `StubService` or the very poor `StubCreditCardService` add nothing. Plain data types (like
  protocol buffer messages) need no double.
- **look for:** in a `<pkg>test` package that doubles one type, double names repeating the package
  or type (`StubCreditCardService`, `FakeCreditCard`); doubles written for plain data structs.
- **note:** with Bazel, the helper package's `go_library` should be marked `testonly = True`.
- **example:** `type StubCreditCardService struct{}` -> `type Stub struct{}`

### google-practices:naming-doubles-multiple-behaviors — Name doubles after their behavior
- **meta:** severity=consider · scope=decl · check=llm
- **rule:** When one kind of double is not enough (for example, one that always fails is also
  needed), name each double after the behavior it emulates: `AlwaysCharges`, `AlwaysDeclines`.
- **look for:** sibling doubles of one type told apart by numbers or vague words (`Stub2`,
  `StubBad`, `OtherStub`) instead of by behavior.
- **example:** `type Stub struct{}; type Stub2 struct{}` -> `type AlwaysCharges struct{}; type AlwaysDeclines struct{}`

### google-practices:naming-doubles-multiple-types — Include the type when doubling several types
- **meta:** severity=consider · scope=decl · check=llm
- **rule:** When the helper package doubles several production types (`Service`, `StoredValue`),
  use more explicit names that include the doubled type: `StubService`, `StubStoredValue`.
- **look for:** a bare `Stub`/`Fake` in a helper package that doubles more than one type, or
  double names that do not say which type they stand in for.
- **example:** `type Stub struct{}` (doubles `Service`, next to a `StoredValue` double) -> `type StubService struct{}`

### google-practices:naming-doubles-local-variables — Name test variables that hold doubles
- **meta:** severity=consider · scope=test · check=llm
- **rule:** In tests, name a variable holding a double so it clearly stands apart from the
  production values around it, for example by prefixing the kind of double: `spyCC`, not `cc`.
- **look for:** doubles stored in variables named like the production value they replace
  (`var cc creditcardtest.Spy` passed as `Processor{CC: cc}` and later asserted on).
- **example:** `var cc creditcardtest.Spy` -> `var spyCC creditcardtest.Spy`

### google-practices:shadowing — Shadowing with := in a nested scope
- **meta:** severity=should · scope=body · check=lint+llm · lint=govet:shadow~declaration of "(?!err")
- **rule:** Reusing a variable with `:=` in the same scope ("stomping") is fine when the old value
  is no longer needed. In a new block, `:=` declares a new variable that shadows the outer one, and
  code after the block still sees the original — the classic bug is a conditional
  `ctx, cancel := context.WithTimeout(ctx, d)`. Declare the extra variable and assign with `=`.
  Intentional shadowing is allowed, but a new name often reads more clearly.
- **look for:** `:=` inside `if`/`for`/`switch`/closures re-declaring a variable that code after
  the block reads expecting the new value (`ctx`, results); an inner `x, err := ...` leaving the
  outer `err` checked later unchanged.
- **skip:** same-scope reuse; shadowing whose outer value is not read again; same-type shadowing
  of names other than `err` — govet reports it.
- **example:** `if short { ctx, cancel := context.WithTimeout(ctx, d); defer cancel() }` -> `var cancel func(); ctx, cancel = context.WithTimeout(ctx, d)`

### google-practices:shadowing/std-package-vars — Variables named after packages
- **meta:** severity=consider · scope=body · check=lint+llm · lint=revive:import-shadowing
- **rule:** Outside very small scopes, don't give variables the names of standard packages
  (`url`, `path`, `time`): below the declaration, that package's functions and values are
  unreachable.
- **look for:** package-named locals or parameters in long functions (`url := "https://..."` at
  the top of a 50-line function), including packages the file does not import yet.
- **skip:** identifiers shadowing an import of the same file — revive reports them (it does not
  exempt the very small scopes the guide allows).
- **example:** `url := cfg.Endpoint` -> `endpoint := cfg.Endpoint`

### google-practices:shadowing/package-naming — Package names that invite shadowing
- **meta:** severity=consider · scope=repo · check=llm · overlaps=google-decisions:package-names
- **rule:** When naming a package, avoid names that clients would likely need to rename on import
  or that would shadow good local variable names at the call site.
- **look for:** packages named like common variables (`count`, `user`, `buf`, `node`) where a
  qualified name (`usercount`) would avoid the clash.
- **example:** `package count` -> `package usercount`

### google-practices:util-packages — Uninformative package names
- **meta:** severity=should · scope=repo · check=lint+llm · lint=revive:package-naming~bad package name · overlaps=google-decisions:package-names
- **rule:** A package name (which matters more for readability than the import path) should
  relate to what the package provides. A bare `util`, `helper`, `common` or similar is usually a
  poor choice, though fine as part of a name: it reads badly at call sites and, if used widely,
  causes needless import conflicts. Judge by how the call site reads.
- **look for:** packages named `helper`, `test`, `lib`, `base`, `stuff`; call sites such as
  `common.SeekStart`, `helper.Marshal(...)`, `test.NewDatabaseFromFile(...)`.
- **skip:** generic words used as part of a name (`spannertest`, `stringutil`); names revive
  already reports (`util`, `common`, `misc`, `types`, `interfaces` and configured extras).
- **example:** `helper.Marshal(curve, x, y)` -> `elliptic.Marshal(curve, x, y)`
