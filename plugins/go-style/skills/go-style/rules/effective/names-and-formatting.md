# Effective Go — Names and Formatting

Effective Go's guidance on gofmt layout, doc comments, and naming packages, getters,
interfaces and multiword identifiers.

### effective:formatting — Formatting
- **meta:** severity=must · scope=repo · check=lint · lint=gofmt · overlaps=google-guide:formatting,google-guide:line-length · conflicts=uber:avoid-overly-long-lines
- **rule:** Leave layout to gofmt: tabs for indentation, aligned columns and comments,
  no parentheses around `if`/`for`/`switch` conditions. If gofmt's answer looks
  wrong, rearrange the program rather than work around it. Go has no line-length
  limit; wrap a line that feels too long and indent the continuation with an extra
  tab.
- **skip:** line length by itself — this guide sets no limit, so `lll` findings do
  not apply under it.
- **example:** `if (x > 0) {` -> `if x > 0 {`

### effective:commentary — Commentary
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:exported~^(?!.*(stutters|is repetitive)),revive:package-comments · overlaps=google-decisions:doc-comments,google-decisions:package-comments
- **rule:** A comment placed immediately before a top-level declaration, with no blank
  line between, is that declaration's doc comment — the primary documentation of a
  package or command. Effective Go defers details to "Go Doc Comments", which asks
  for a package comment on every package and a doc comment on every exported name.
  Line comments (`//`) are the norm; block comments (`/* */`) serve mainly as
  package comments, within an expression, or to disable large swaths of code.
- **look for:** a blank line between an intended doc comment and its declaration
  (revive only sees exported names and the package clause); `/* */` blocks where
  `//` comments are the norm.
- **skip:** missing doc comments on exported names, doc comments not starting with the
  name ("Go Doc Comments" convention), missing or detached package comments — revive
  reports them.

### effective:package-names/package — Package names: choosing the name
- **meta:** severity=should · scope=repo · check=lint+llm · lint=revive:package-naming~(underscore|MixedCaps),revive:package-directory-mismatch · overlaps=google-decisions:package-names
- **rule:** A package name is short, concise and evocative: one lower-case word with
  no underscores or mixedCaps, matching the base name of its source directory
  (`encoding/base64` is package `base64`). Err on the side of brevity, since every
  user types it. Don't worry about collisions a priori: the name is only the default
  for imports, and an importer can choose another name locally.
- **look for:** long or compound names (`stringutilities`, `datastoremanager`) where
  one evocative word would do.
- **skip:** underscores, mixedCaps and directory mismatches — revive reports them;
  `_test` packages; names that collide with other packages, std ones included.

### effective:package-names/qualified — Package names: exported names and the qualifier
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:exported~(stutters|is repetitive),revive:dot-imports · overlaps=google-decisions:repetitive-with-package,google-decisions:import-dot
- **rule:** Clients always refer to exported names through the package name, so use it
  as context instead of repeating it: `bufio.Reader`, not `bufio.BufReader`; when
  `Ring` is the only exported type of package `ring`, its constructor is `ring.New`,
  not `ring.NewRing`. Long names don't automatically read better (`once.Do`, not
  `once.DoOrWaitUntilDone`); a helpful doc comment is often worth more. Avoid
  `import .`, except in tests that must run outside the package they test.
- **look for:** `NewFoo` constructors in package `foo` whose only exported type is
  `Foo`; the package name repeated mid-name or abbreviated (`bufio.BufReader`);
  needlessly long exported names.
- **skip:** names starting with the package name and dot imports — revive reports
  them (this guide allows dot imports in tests that must run outside the package).
- **example:** `widget.NewWidget()` -> `widget.New()`

### effective:Getters — Getters
- **meta:** severity=should · scope=decl · check=llm · custom=getter-prefix · overlaps=google-decisions:getters,google-practices:function-name-conventions
- **rule:** Getters and setters are fine, but a getter carries no `Get` prefix: for an
  unexported field `owner` the getter is `Owner()` — the upper-case export already
  tells method from field — and a setter, if needed, is `SetOwner()`.
- **look for:** exported methods `GetX()` with no parameters that return a field or a
  trivially derived value.
- **skip:** `Get` methods that take a key or perform a lookup or fetch; generated code
  (protobuf `GetX()` accessors); names an external interface requires.
- **example:** `func (o *Obj) GetOwner() User` -> `func (o *Obj) Owner() User`

### effective:interface-names/er-suffix — Interface names: one-method interfaces
- **meta:** severity=should · scope=decl · check=llm · custom=iface-name-affix
- **rule:** By convention a one-method interface is named after its method plus an -er
  suffix, or a similar modification that builds an agent noun: `Reader`, `Writer`,
  `Formatter`, `CloseNotifier`.
- **look for:** single-method interfaces named with `I`/`Interface` affixes
  (`IReader`, `ReaderInterface`) or after something other than the behavior
  (`FileService` holding only `Read`).
- **skip:** interfaces with several methods; established agent nouns that don't
  literally add -er (`Handler` for `ServeHTTP`).
- **example:** `type ReadInterface interface { Read(p []byte) (int, error) }` -> `type Reader interface { ... }`

### effective:interface-names/canonical-methods — Interface names: canonical method names
- **meta:** severity=should · scope=decl · check=lint+llm · lint=govet:stdmethods · custom=canonical-method-sig
- **rule:** `Read`, `Write`, `Close`, `Flush`, `String` and other well-known method names
  have canonical signatures and meanings. Don't give a method one of those names
  unless it has the same signature and meaning; conversely, a method with the
  meaning of a well-known one takes its name and signature — `String`, not
  `ToString`.
- **look for:** `ToString()`/`AsString()` methods; `String`, `Read`, `Write` or `Close`
  with non-standard signatures (`Write(s string)`, `String() (string, error)`) or
  unrelated meanings.
- **skip:** signature errors on `Format`, `MarshalJSON`, `ReadByte`, `Seek`, `WriteTo`,
  `Unwrap`, `Is`, `As` and the other names vet `stdmethods` checks; `Close()` or
  `Flush()` without an error result (std has both forms).
- **example:** `func (p Point) ToString() string` -> `func (p Point) String() string`

### effective:mixed-caps — MixedCaps
- **meta:** severity=should · scope=decl · check=lint · lint=revive:var-naming~underscores,revive:var-naming~ALL_CAPS · overlaps=google-guide:mixed-caps,google-decisions:underscores
- **rule:** Write multiword names in `MixedCaps` or `mixedCaps`, not with underscores.
- **skip:** `Test`/`Benchmark`/`Example`/`Fuzz` function names in `_test.go` files
  (revive ignores them); generated code; identifiers that mirror cgo or OS names.
- **example:** `max_retries`, `MAX_RETRIES` -> `maxRetries`, `MaxRetries`
