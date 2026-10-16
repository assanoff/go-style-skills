# Effective Go — Data, Initialization and Methods

Effective Go on allocating with `new`, `make` and composite literals, on arrays,
slices, maps, printing and `append`, on constants and `init`, and on pointer versus
value receivers.

### effective:allocation_new — Allocation with new
- **meta:** severity=consider · scope=decl · check=llm
- **rule:** `new(T)` returns a pointer to a zeroed `T`, so design data structures whose
  zero value is ready to use without further initialization, like `bytes.Buffer`
  (an empty buffer) or `sync.Mutex` (unlocked). The property is transitive: a struct
  made of such fields works straight from `new` or a plain `var` declaration.
- **look for:** types that need an `Init` method or a constructor only to set fields
  that could have useful zero values; methods that break on the zero value where
  lazy initialization would make it usable (writing to a nil map field); `*sync.Mutex`
  fields allocated in a constructor where a `sync.Mutex` value would do.
- **skip:** types whose invariants genuinely need constructor arguments.
- **note:** Since Go 1.26 `new` also takes an expression for the initial value:
  `new(int64(300))`.

### effective:composite_literals — Constructors and composite literals
- **meta:** severity=consider · scope=body · check=llm · custom=new-then-assign · overlaps=google-decisions:literal-formatting,google-practices:vardeclcomposite
- **rule:** When the zero value isn't enough, initialize with a composite literal rather
  than `new` followed by field-by-field assignments, and return its address directly
  (returning the address of a local is safe). Labeled `field: value` elements may
  come in any order and omitted fields get their zero values; `new(File)` and
  `&File{}` are equivalent. Array, slice and map literals take index or key labels.
- **look for:** `x := new(T)` (or `var x T`) followed by a run of `x.f = ...`
  assignments a literal could express, especially assignments of zero values
  (`f.dirinfo = nil`).
- **skip:** fields that depend on intermediate computation or conditions; keyed vs
  positional fields for other packages' types (vet `composites`, Google's
  literal-field-names).
- **example:** `f := new(File); f.fd = fd; f.name = name; return f` -> `return &File{fd: fd, name: name}`

### effective:allocation_make — Allocation with make
- **meta:** severity=should · scope=body · check=lint+llm · lint=staticcheck:S1019 · custom=new-ref-type
- **rule:** `make` creates only slices, maps and channels, and returns an initialized
  (not zeroed) value of type `T`, not `*T`. `new([]int)` gives a pointer to a nil
  slice, which is rarely useful; to get an explicit pointer, allocate with `new` or
  take a variable's address.
- **look for:** `new([]T)`, `new(map[K]V)`, `new(chan T)`; a pointer to a slice or map
  created only to assign `*p = make(...)`.
- **skip:** redundant `make` arguments, such as a capacity equal to the length —
  staticcheck S1019 reports them.
- **example:** `p := new([]int); *p = make([]int, 100, 100)` -> `v := make([]int, 100)`

### effective:arrays — Arrays
- **meta:** severity=should · scope=decl · check=llm
- **rule:** Arrays are values: assigning one copies all its elements, a function gets
  a copy rather than a pointer, and the size is part of the type (`[10]int` and
  `[20]int` differ). Passing a pointer to an array avoids the copy but isn't
  idiomatic either — use slices. Arrays suit explicit dimensions, detailed memory
  layout, or avoiding an allocation.
- **look for:** parameters or results typed `[N]T` or `*[N]T` that carry general
  sequences; large arrays copied by value in assignments or calls.
- **skip:** fixed-size values such as hashes, keys and addresses (`[32]byte`), small
  matrices, arrays used as map keys.
- **example:** `func Sum(a *[3]float64) (sum float64)` -> `func Sum(a []float64) (sum float64)`

### effective:slices — Slices
- **meta:** severity=should · scope=decl · check=llm
- **rule:** Pass sequences as slices. A slice refers to an underlying array, so a
  function taking a slice (like `Read(buf []byte)`, rather than a pointer and a
  count) can change elements the caller sees, and the slice's length bounds the
  operation (`f.Read(buf[0:32])`). The slice header — pointer, length, capacity — is
  passed by value, so a function that may grow or reallocate a slice must return the
  result.
- **look for:** buffers passed as a pointer plus a length; helpers that append to or
  reslice a slice parameter without returning it, leaving the caller with the old
  length; callers that drop such a returned slice.
- **skip:** functions that only modify existing elements in place.
- **example:** `func read(buf *[]byte, n int) error` -> `func read(buf []byte) (int, error)`

### effective:two_dimensional_slices — Two-dimensional slices
- **meta:** severity=should · scope=body · check=llm
- **rule:** A 2D slice is a slice of slices whose rows may differ in length. If rows
  might grow or shrink, allocate each one independently so a row can't overwrite the
  next; if their sizes are fixed, one allocation sliced into rows can be more
  efficient.
- **look for:** rows carved from one shared buffer
  (`picture[i], pixels = pixels[:x], pixels[x:]`) that are later appended to.
- **skip:** shared-buffer rows that are never resized.
- **note:** A full slice expression (`pixels[:x:x]`, Go 1.2+) caps each row's
  capacity, so an `append` reallocates instead of overwriting the next row.

### effective:maps — Maps
- **meta:** severity=should · scope=body · check=lint+llm · lint=staticcheck:S1033
- **rule:** Fetching a missing key returns the zero value of the element type. When a
  missing entry must be told apart from a zero value, use the comma-ok form
  (`seconds, ok := timeZone[tz]`, or `_, present := m[k]` for presence only); plain
  indexing is fine when the zero value is the right answer, as with a `map[T]bool`
  used as a set. `delete` is safe for absent keys.
- **look for:** `m[k] == 0`, `m[k] == ""` or `m[k] != nil` used as presence tests
  where a zero value is legitimate; a presence check followed by a second lookup of
  the same key.
- **skip:** presence guards around `delete` — staticcheck S1033 reports them.
- **example:** `if timeZone[tz] == 0 { unknown() }` -> `if _, ok := timeZone[tz]; !ok { unknown() }`

### effective:printing — Printing
- **meta:** severity=should · scope=body · check=lint+llm · lint=govet:printf~recursive,govet:printf~missing \.\.\. · custom=string-method-value-print
- **rule:** A `String() string` method sets a type's default format. Inside it, don't
  format the receiver with a verb wanting a string (`%s`, `%q`, `%v`) or `Sprint`,
  which recurses forever; convert to the underlying type (`string(m)`) or use a verb
  such as `%f`. Use a value receiver if values, not only pointers, are printed. A
  wrapper handing its `...` arguments to another print function passes `v...`.
- **look for:** `String` on `*T` while `T` values are printed with `%v` or `Println`
  (the method is silently not used); recursion through helpers vet can't follow.
- **skip:** direct recursive formatting of the receiver inside `String` and missing
  `...` in print wrappers — vet `printf` reports them.
- **example:** `fmt.Sprintf("MyString=%s", m)` -> `fmt.Sprintf("MyString=%s", string(m))`
- **note:** `...interface{}` is `...any` since Go 1.18; the guide's `Min(a ...int)`
  predates the built-in `min` and `max` (Go 1.21).

### effective:append — Append
- **meta:** severity=should · scope=body · check=lint+llm · lint=staticcheck:S1011,gocritic:appendAssign
- **rule:** `append` returns the updated slice because the underlying array may change,
  so use its result, normally assigning it back to the same slice
  (`x = append(x, 4, 5, 6)`). Append a whole slice in one call with `...`
  (`x = append(x, y...)`).
- **look for:** two slices appended from the same base (`a := append(s, 1)`,
  `b := append(s, 2)`) and then used as if independent — they may share one array.
- **skip:** element-by-element append loops (staticcheck S1011) and results assigned
  to a different slice (gocritic `appendAssign`) — linters report them.

### effective:constants — Constants
- **meta:** severity=consider · scope=decl · check=llm
- **rule:** Create enumerated constants with `iota`; since expressions are implicitly
  repeated, patterns like `KB ByteSize = 1 << (10 * iota)` stay short. A `String`
  method on the user-defined type lets its values, scalars included, format
  themselves when printed.
- **look for:** related constants numbered by hand or left untyped where a named type
  with `iota` would express the set; enum-like types printed in logs or errors
  without a `String` method.
- **skip:** values fixed by an external protocol or storage format, where explicit
  numbers are clearer.
- **note:** `golang.org/x/tools/cmd/stringer` generates `String` methods for `iota`
  types.

### effective:init — The init function
- **meta:** severity=consider · scope=repo · check=llm · conflicts=uber:avoid-init/side-effects
- **rule:** Package-level variables can be initialized with expressions computed at run
  time, so set up state in declarations where possible. Use `init` (a file may have
  several) for initialization that cannot be expressed as a declaration and to
  verify or repair program state before real execution begins; it runs after all
  package variables are initialized, which happens after imported packages are.
- **look for:** `init` bodies that only assign package variables that a
  `var x = expr` declaration, possibly calling a helper, could initialize.
- **skip:** `init` that checks or repairs configuration or registers flags, as in the
  guide's own example.
- **note:** Uber says to avoid `init` and to keep it free of environment access and
  I/O; Effective Go's example reads environment variables and calls `log.Fatal`.

### effective:pointers_vs_values — Pointers vs. Values
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:modifies-value-receiver,staticcheck:SA4005 · overlaps=google-decisions:receiver-type
- **rule:** Methods can be defined on any named type except a pointer or an interface.
  Value methods can be invoked on values and pointers, pointer methods only on
  pointers (for addressable values the compiler inserts `&`). A method that must
  modify its receiver needs a pointer receiver — with a value receiver the change
  hits a copy and is lost — and then only `*T` satisfies interfaces that need the
  method, so pass `&v`.
- **look for:** value-receiver methods returning an updated copy of a slice-typed
  receiver where a pointer receiver would update the caller's value (the guide's
  `ByteSlice.Append` turned into `Write`).
- **skip:** assignments to a value receiver's fields — revive and staticcheck SA4005
  report them; methods that copy, modify and return the receiver (`WithX` style).
- **example:** `func (c Counter) Inc() { c.n++ }` -> `func (c *Counter) Inc() { c.n++ }`
