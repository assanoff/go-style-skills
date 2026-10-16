# Effective Go — Interfaces, the Blank Identifier and Embedding

Effective Go on small interfaces, type assertions, exporting interfaces instead of
implementation types, uses of the blank identifier, and embedding.

### effective:interfaces — Interfaces
- **meta:** severity=consider · scope=decl · check=lint+llm · lint=interfacebloat · overlaps=google-decisions:interfaces,google-practices:designing-effective-interfaces
- **rule:** An interface specifies behavior: if something can do this, it can be used
  here. Interfaces with only one or two methods are common and are usually named
  after the method (`io.Writer` for `Write`); a type can implement several
  interfaces at once (`sort.Interface` plus a `String` method).
- **look for:** interfaces bundling many methods whose users need only one or two.
- **skip:** interfaces with more than 10 methods — interfacebloat reports them.

### effective:interface_conversions — Interface conversions and type assertions
- **meta:** severity=should · scope=body · check=lint · lint=forcetypeassert
- **rule:** A type assertion `value.(T)` crashes the program with a run-time error if
  the value doesn't hold a `T`. Guard it with the comma-ok form
  (`str, ok := value.(string)`; on failure `str` is the zero value) or use a type
  switch. The target may be a concrete type or another interface the value can be
  converted to.
- **skip:** assertions meant to panic on failure, such as the re-panic idiom
  `err = e.(Error)` in the guide's recover example.
- **example:** `str := value.(string)` -> `str, ok := value.(string); if !ok { ... }`

### effective:generality — Generality
- **meta:** severity=consider · scope=decl · check=llm · conflicts=google-decisions:interfaces,google-practices:designing-effective-interfaces
- **rule:** If a type exists only to implement an interface and will never have exported
  methods beyond it, don't export the type: export the interface and have the
  constructor return an interface value (`crc32.NewIEEE` and `adler32.New` both
  return `hash.Hash32`). That shows the value has no behavior beyond the interface,
  avoids repeating the method docs on every implementation, and makes switching
  implementations a change to the constructor call only.
- **look for:** exported implementation types whose exported methods are exactly an
  interface's, returned by constructors of interchangeable implementations.
- **skip:** types whose callers need extra exported methods or fields.
- **note:** Google's guides default to "accept interfaces, return concrete types" and
  return interfaces only for encapsulation, runtime-selected implementations or
  breaking import cycles; they take precedence in multi-guide runs.

### effective:blank_assign — The blank identifier in multiple assignment
- **meta:** severity=must · scope=body · check=lint+llm · lint=errcheck · overlaps=google-decisions:handle-errors
- **rule:** In a multiple assignment, discard values the program doesn't need with `_`
  rather than a dummy variable (`if _, err := os.Stat(path); ...`). Never use it to
  ignore an error: always check error returns — they are provided for a reason.
- **look for:** errors discarded with `_` (`fi, _ := os.Stat(path)`) and the other
  result then used.
- **skip:** error results ignored without any assignment — errcheck reports them (and
  `_` discards too when its check-blank option is on); calls documented never to fail
  (`bytes.Buffer.Write`, `strings.Builder.WriteString`, `hash.Hash.Write`).
- **example:** `fi, _ := os.Stat(path)` -> `fi, err := os.Stat(path); if err != nil { return err }`
- **note:** The guide's `os.IsNotExist(err)` does not see wrapped errors; use
  `errors.Is(err, fs.ErrNotExist)`.

### effective:blank_unused — Unused imports and variables
- **meta:** severity=should · scope=body · check=llm · custom=blank-silencer
- **rule:** Blank assignments that silence unused-import or unused-variable errors
  (`var _ = fmt.Printf`, `_ = fd`) mark work in progress: the import or variable
  should eventually be used or removed. Until then, the import silencers go right
  after the imports with a comment, so they are easy to find and clean up.
- **look for:** `var _ = pkg.Symbol` declarations and `_ = x` statements that exist
  only to keep an unused import or variable compiling.
- **skip:** `var _ I = (*T)(nil)` interface checks (effective:blank_implements); `_ =`
  statements that evaluate an expression on purpose, such as a bounds-check hint
  (`_ = b[7]`).

### effective:blank_implements — Interface checks
- **meta:** severity=consider · scope=decl · check=llm · custom=redundant-iface-assert · conflicts=uber:verify-interface-compliance
- **rule:** Most interface conversions are static, so the compiler checks them. When the
  package contains no such conversion — e.g. a type meant to satisfy
  `json.Marshaler`, which the encoder finds only by a run-time assertion — guarantee
  it with `var _ json.Marshaler = (*RawMessage)(nil)`. Don't do this for every type
  that satisfies an interface: by convention such declarations appear only when no
  static conversion exists, which is rare.
- **look for:** `var _ I = (*T)(nil)` where the same package already assigns, passes
  or returns a `*T` as an `I`; types found only by run-time assertions (custom
  `MarshalJSON`, `MarshalText`) and left unchecked, where a receiver or signature
  slip would silently disable them.
- **skip:** checks on exported types whose conversions happen only in other packages.

### effective:embedding — Embedding
- **meta:** severity=consider · scope=decl · check=llm · conflicts=uber:avoid-embedding-types-in-public-structs
- **rule:** Compose interfaces by embedding them (`ReadWriter` embeds `Reader` and
  `Writer`) rather than re-listing their methods, and embed a type in a struct to
  promote its methods rather than writing forwarding methods. Embedding is not
  subclassing: a promoted method runs with the inner value as its receiver. Embedded
  pointers must point to valid values before use, and an outer field or method hides
  a same-named one deeper in the type.
- **look for:** interfaces re-listing another interface's methods; methods that only
  forward to the same method of a field; embedded pointers left nil by constructors;
  inner methods expected to call an outer type's "override".
- **skip:** forwarding methods written to expose only part of an inner type's API.
- **note:** Uber advises against embedding types in exported structs (it leaks
  implementation details); by guide priority this rule wins over that one.
