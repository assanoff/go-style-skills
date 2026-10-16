# Google Go Style Guide — Core guidelines

The guidelines all Go code is expected to follow: gofmt formatting, MixedCaps names, no
fixed line length, names that respect their context, and local consistency where the
guide is silent.

### google-guide:formatting — Formatting
- **meta:** severity=must · scope=repo · check=lint · lint=gofmt
- **rule:** Every Go source file must match the output of `gofmt`.
- **skip:** reviewers skip it — gofmt reports every violation outside generated files.

### google-guide:formatting/generated — Formatting of generated code
- **meta:** severity=should · scope=repo · check=llm
- **rule:** Generated code should generally be gofmt-formatted too (e.g. with
  `go/format.Source`), since people browse it like any other code.
- **look for:** generators writing `.go` files from `text/template`, `fmt.Fprintf` or a
  buffer without passing the bytes through `format.Source` (or `imports.Process`);
  committed generated files that are not gofmt-clean.
- **skip:** output of well-known generators that already format it.
- **note:** golangci-lint excludes files headed `// Code generated ... DO NOT EDIT.` from
  formatter checks, so gofmt never reports them.

### google-guide:mixed-caps — MixedCaps
- **meta:** severity=must · scope=decl · check=lint+llm · lint=revive:var-naming~underscores,revive:var-naming~ALL_CAPS,gocritic:captLocal
- **rule:** Multi-word names use `MixedCaps` or `mixedCaps`, never underscores, even when
  that breaks other languages' conventions: an exported constant is `MaxLength` (not
  `MAX_LENGTH`), an unexported one `maxLength` (not `max_length`). Local variables count
  as unexported, so they start lowercase.
- **look for:** capitalized locals declared in function bodies (captLocal flags them only
  with `paramsOnly: false`); all-caps multi-word names without underscores (`MAXLENGTH`),
  which revive misses.
- **skip:** google-decisions:underscores exceptions — Test, Benchmark and Example function
  names in `_test.go` files, packages imported only by generated code, low-level OS/cgo
  identifiers mirroring `syscall`; file names; names revive or captLocal already report.
- **example:** `const MAX_LENGTH = 10` -> `const MaxLength = 10`

### google-guide:line-length — Line length
- **meta:** severity=should · scope=body · check=llm · custom=line-split · conflicts=uber:avoid-overly-long-lines
- **rule:** Go has no fixed line length. Refactor a line that feels too long rather than
  splitting it; a line already as short as practical may stay long. Do not split a line
  before an indentation change (function signature, `if`/`for` condition) or to fit a
  long string such as a URL into shorter pieces.
- **look for:** signatures or conditions wrapped so continuation lines align with the
  block body; string or URL literals cut into `"..." +` pieces; calls broken at arbitrary
  points purely for width where a local variable would shorten them.
- **skip:** long lines as such — no column limit applies, so ignore `lll` and 99-column
  rules; breaks at semantic boundaries, e.g. arguments grouped after a long format string.

### google-guide:naming — Naming
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:exported~(stutters|is repetitive)
- **rule:** Go names run shorter than in many languages, but the usual principles apply: a
  name should not feel repetitive where it is used, should take its context (package,
  type, receiver, function) into account, and should not repeat concepts that are
  already clear. google-decisions' naming rules give the specifics.
- **look for:** names repeating their type (`nameString`, `userSlice`); methods or fields
  repeating the receiver or struct (`(p *Project) ProjectName()`); locals repeating what
  the package or function already says (`adsTargetingID` in package `targeting`); long
  names for short-lived locals (`dbLoadError` where `err` would do).
- **skip:** exported names repeating the package — revive reports them; a type word needed
  because one value appears in two forms in a scope (`limitRaw`, `limit`).
- **example:** `func (p *Project) ProjectName() string` -> `func (p *Project) Name() string`

### google-guide:local-consistency — Local consistency
- **meta:** severity=should · scope=repo · check=llm
- **rule:** Where the guide is silent, authors may choose, unless nearby code (file or
  package, sometimes team or directory) has a consistent stance — then follow it. Valid
  local choices: `%s` vs `%v` for errors, buffered channels instead of mutexes; invalid:
  line-length limits, assertion-based test libraries. Local style never justifies a
  change that worsens a guide deviation, spreads it to more APIs or files, or adds a bug:
  clean up first or in the same change, or find an alternative that doesn't worsen it.
- **look for:** new code taking a different stance from its file or package on an open
  point (mixing `%v` and `%s` for errors, a mutex where the package uses channels); a
  guide deviation copied into new files or exported APIs "for consistency"; line-length
  limits or assertion libraries defended as local style.
- **skip:** existing deviations confined to one file that the change doesn't worsen —
  suggest filing a bug instead of fixing them in this change.
