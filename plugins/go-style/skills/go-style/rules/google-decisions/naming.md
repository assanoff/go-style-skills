# Google Style Decisions — Naming

Names: underscores, package, receiver, constant and variable names, initialisms, getters,
and repetition between a name and its package, type or context.

### google-decisions:underscores — Underscores
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:var-naming~underscores · overlaps=google-guide:mixed-caps · conflicts=uber:prefix-unexported-globals-with-_
- **rule:** Names should not contain underscores; multi-word names use MixedCaps. Exceptions:
  package names imported only by generated code; Test, Benchmark and Example function names in
  `*_test.go` files; rare low-level OS or cgo interop code that reuses foreign identifiers (as
  `syscall` does). File names are not identifiers and may contain underscores.
- **look for:** leading-underscore names such as `_defaultPort` or `_maxRetries` (Uber's
  prefix for unexported globals) — revive does not flag a leading underscore.
- **skip:** the exceptions above; other underscores (revive reports them); ALL_CAPS constants
  (constant-names) and package names (package-names).
- **example:** `const _defaultPort = 8080` -> `const defaultPort = 8080`

### google-decisions:package-names/form — Package names: lowercase letters and digits
- **meta:** severity=must · scope=repo · check=lint · lint=revive:package-naming~(underscore|MixedCaps)
- **rule:** Package names use only lowercase letters and digits (`k8s`, `oauth2`); multi-word
  names stay unbroken (`tabwriter`, not `tabWriter` or `tab_writer`). Underscores are allowed
  only in packages imported solely by generated code and in test packages: the `_test` suffix
  for black-box tests and package examples (`linkedlist_test`, not `linked_list_test`) and
  underscored integration-test packages (`linked_list_service_test`).
- **skip:** integration-test packages such as `linked_list_service_test` (revive strips only
  the final `_test` and flags them); packages imported only by generated code.
- **example:** `package tab_writer` -> `package tabwriter`

### google-decisions:package-names/uninformative — Package names: informative and hard to shadow
- **meta:** severity=should · scope=repo · check=lint+llm · lint=revive:package-naming~(bad package name|root level|conflicts with)
- **rule:** Choose concise, informative names that callers will not want to rename on import:
  avoid `util`, `utility`, `common`, `helper`, `model`, `testhelper` and the like, and avoid
  names likely to be shadowed by common local variable names (`usercount`, not `count`).
- **look for:** grab-bag names revive's exact-name list misses (`helper`, `model`, `utility`,
  `testhelper`, `base`); package names that are common variable names (`count`, `user`, `buf`,
  `data`); long multi-word names that are not concise.
- **skip:** names revive reports; revive's extra list also flags `api`, which the guide does
  not name — judge it on informativeness.
- **note:** revive's collision-with-std finding (`http`, `json`, `url`) is mapped here: such
  names force renames, and good package names should not need renaming (import-renaming).

### google-decisions:receiver-names — Receiver names
- **meta:** severity=must · scope=decl · check=lint+llm · lint=revive:receiver-naming,staticcheck:ST1016
- **rule:** Receiver names must be short (usually one or two letters), an abbreviation of the
  type, the same for every method of the type, and never `_` (omit an unused receiver's name);
  `this` and `self` do not qualify.
- **look for:** receivers that do not abbreviate the type (`x *Client`, `obj *Tray`);
  three-letter names where one or two letters would do; different names for one type across
  the files of a package (revive checks one file at a time; ST1016 covers it once enabled).
- **skip:** `_`, `this`/`self`, names longer than three letters and in-file inconsistency —
  revive reports them.
- **example:** `func (info *ResearchInfo) Name()` -> `func (ri *ResearchInfo) Name()`

### google-decisions:constant-names/mixedcaps — Constant names: MixedCaps, no K prefix
- **meta:** severity=must · scope=decl · check=lint+llm · lint=revive:var-naming~ALL_CAPS · custom=const-k-prefix · overlaps=google-guide:mixed-caps
- **rule:** Constants use MixedCaps like every other Go name (exported `MaxPacketSize`,
  unexported `maxPacketSize`), even where other languages use ALL_CAPS, and take no `k`/`K`
  prefix.
- **look for:** `k`/`K`-prefixed constants (`kMaxBufferSize`, `KMaxUsersPergroup`); all-caps
  names without underscores, which revive misses (`TIMEOUT`, `MAXSIZE`).
- **skip:** ALL_CAPS names containing underscores (revive reports them, as ALL_CAPS or as
  underscores); true initialisms (`URL`, `EOF`).
- **example:** `const MAX_PACKET_SIZE = 512` -> `const MaxPacketSize = 512`

### google-decisions:constant-names/role — Constant names: role, not value
- **meta:** severity=should · scope=decl · check=llm
- **rule:** Name a constant for what its value denotes, not as a derivative of the value. A
  constant with no role apart from its value is unnecessary; use the literal instead.
- **look for:** names that restate the literal (`Twelve = 12`, `Port8080 = 8080`,
  `UserNameColumn = "username"`, `GroupColumn = "group"`).
- **example:** `const Twelve = 12` -> `const MonthsPerYear = 12`

### google-decisions:initialisms — Initialisms
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:var-naming~^(?!don't use)
- **rule:** Each initialism or acronym in a name keeps a single case: `URL` or `url`, never
  `Url`; likewise `ID`, `DB`. With several initialisms each is uniform on its own (`XMLAPI`,
  `xmlAPI`). Initialisms containing a lowercase letter keep their prose form (`gRPC`, `iOS`,
  `DDoS`) unless the first letter must change for exportedness; then the whole initialism takes
  one case (`GRPC`, `IOS`, `ddos`). Ordinary abbreviations stay word-cased (`Txn`, not `TXN`).
- **look for:** initialisms outside revive's list (`Db`, `Grpc`, `Ios`, `DDOS`, `Aws`, `Jwt`);
  mixed runs revive cannot split (`XMLApi`, `XmlAPI`); all-caps abbreviations (`TXN`);
  interface method names, which revive does not check.
- **skip:** cases revive reports (its list covers ID, URL, HTTP, JSON, API, XML, SQL and more).
- **example:** `func newDbConn()` -> `func newDBConn()`

### google-decisions:getters — Getters
- **meta:** severity=should · scope=decl · check=llm · custom=getter-prefix
- **rule:** Function and method names should not start with `Get`/`get`; start with the noun
  (`Counts`, not `GetCounts`), unless the concept itself involves "get" (an HTTP GET). For
  expensive computation or remote calls, a verb such as `Compute` or `Fetch` tells the reader
  the call may take time, block or fail.
- **look for:** `GetX`/`getX` functions and methods that return a value; `Get…` names on calls
  that hit the network, disk or a heavy computation, where `Fetch`/`Load`/`Compute` would warn.
- **skip:** HTTP GET handlers and clients; names required by an interface defined elsewhere
  (e.g. `GetObjectKind`); generated code such as protobuf getters.
- **example:** `func (u *User) GetName() string` -> `func (u *User) Name() string`

### google-decisions:variable-names — Variable names
- **meta:** severity=should · scope=body · check=llm
- **rule:** Name length tracks scope size (roughly: a word or a character or two for 1–7
  lines, more words toward file scope or when many similar values share it). Name a local for
  what it holds and how it is used here, not where it came from (often not the struct or proto
  field name). Start from one word, add words only to disambiguate (`userCount`,
  `projectCount`), do not drop letters (`Sandbox`, not `Sbx`), and omit words the context
  already gives.
- **look for:** cryptic abbreviations living across a large scope or at package level (`sbx`,
  `cnt`, `usrMgr`); long multi-word names in a tiny scope; locals repeating the enclosing
  method or type (`userCount` inside `UserCount()`).
- **skip:** short names that stay clear in any scope (`db`, `ctx`, `err`); single letters (v).
- **example:** `sbxCfg := loadSbx()` -> `sandbox := loadSandbox()`

### google-decisions:v — Single-letter variable names
- **meta:** severity=should · scope=body · check=llm
- **rule:** Use single-letter names only where the full word is obvious and repeating it would
  be noise: method receivers (one or two letters), familiar names for common types (`r` for
  `io.Reader` or `*http.Request`, `w` for `io.Writer` or `http.ResponseWriter`), integer loop
  indices and coordinates (`i`, `x`, `y`), and short loops over obvious items
  (`for _, n := range nodes`).
- **look for:** single letters whose meaning is not obvious from type or context and that live
  long enough that a reader must look back (`p := loadPolicy()` used 40 lines later);
  several unrelated single-letter values in one scope (`a, b, c`).
- **skip:** the conventional cases above; scopes of a few lines.
- **example:** `p := loadPolicy()` used far below -> `policy := loadPolicy()`

### google-decisions:repetition — Repetition: repetitive code
- **meta:** severity=should · scope=body · check=llm · overlaps=google-guide:concision
- **rule:** Go code should avoid unnecessary repetition. Besides repetitive names (the
  repetitive-* rules), code itself is repetitive when the same or a similar segment appears
  several times in close proximity.
- **look for:** the same or near-identical block repeated within a function or in adjacent
  functions, differing only in a value or field — a candidate for a loop, table or helper.
- **skip:** two short similar blocks where a helper would obscure more than it saves; table
  entries in tests.

### google-decisions:repetitive-with-package — Package vs. exported symbol name
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:exported~(stutters|is repetitive) · custom=pkg-name-in-symbol · overlaps=google-guide:naming
- **rule:** Callers always see the package name, so exported names should not repeat it. If a
  package exports a single type named after the package, its constructor is `New`.
- **look for:** the package name inside or at the end of an exported name
  (`widget.NewWidget` -> `widget.New`, `widget.NewWidgetWithName` -> `widget.NewWithName`,
  `db.LoadFromDatabase` -> `db.Load`); a long package name repeated in its symbols, where a
  shorter package or import name is the better fix.
- **skip:** exported names that start with the package name — revive reports them (it skips
  `main` and test files).
- **example:** `widget.NewWidget(opts)` -> `widget.New(opts)`

### google-decisions:repetitive-with-type — Variable name vs. type
- **meta:** severity=should · scope=body · check=llm · custom=type-in-name · overlaps=google-guide:naming
- **rule:** Do not encode a variable's type in its name; the compiler and usually the reader
  know it. Clarify the type only when one value appears in two forms in the same scope, using a
  word like `raw`/`parsed` or the representation (`limitStr` and `limit`).
- **look for:** type words in names: `numUsers int` (-> `users`), `usersInt`, `nameString`,
  `userSlice`, `userMap`, `primaryProject *Project` (-> `primary`).
- **skip:** two forms of one value in scope (`ageString` and `age`, `limitRaw` and `limit`).
- **example:** `var nameString string` -> `var name string`

### google-decisions:repetitive-in-context — External context vs. local names
- **meta:** severity=should · scope=decl · check=llm · custom=method-repeats-receiver · overlaps=google-guide:naming
- **rule:** Names should not repeat what their context already says: the package name, import
  path, type, method, function and even file name qualify every name inside them. Judge
  repetition as the caller sees the name, not in isolation.
- **look for:** methods repeating the receiver type (`(p *Project) ProjectName()`); types
  repeating words of the package path (`AdsTargetingRevenueReport` in
  `ads/targeting/revenue/reporting`, `DBConnection` in package `sqldb`).
- **skip:** local variable names (variable-names covers them); a repeated word that
  disambiguates two similar names in the same context.
- **example:** `func (p *Project) ProjectName() string` -> `func (p *Project) Name() string`
