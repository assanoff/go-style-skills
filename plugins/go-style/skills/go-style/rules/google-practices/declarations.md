# Google Go Style Best Practices — Declarations

Variable declarations: `:=` versus `var`, zero values, composite literals, size hints and
channel direction.

### google-practices:vardeclinitialization — Initialization
- **meta:** severity=consider · scope=body · check=llm · custom=var-short-decl
- **rule:** For consistency, initialize a new local variable that gets a non-zero value with
  `:=` rather than `var x = value`.
- **look for:** `var x = expr` (one name, no type, non-zero value) inside function bodies.
- **skip:** zero-value declarations `var x T` (vardeclzero); zero initializers such as
  `var n = 0`, since `var n int` vs `n := 0` is a non-decision in google-decisions;
  package-level `var`, where `:=` is not allowed.
- **example:** `var i = 42` -> `i := 42`

### google-practices:vardeclzero — Declaring variables with zero values
- **meta:** severity=should · scope=body · check=lint+llm · lint=revive:var-declaration~zero value · custom=zero-value-decl
- **rule:** Declare an empty value that is ready for later use (an unmarshal target, an
  accumulator) as `var x T`, not with clunky spelled-out zeros such as `Point{X: 0, Y: 0}`,
  `[4]byte{0, 0, 0, 0}` or `[]int(nil)`. For a pointer, `new(T)` and `&T{}` are both fine.
  If a composite is returned by pointer or every use takes its address, declare it as a
  pointer from the start; declare protobuf messages as pointers (only `*pb.Msg` implements
  `proto.Message`). Maps must be made before writes; reading a nil map is fine.
- **look for:** literals made only of zero values; `[]T(nil)` initializers; `var c T` ...
  `return &c`; `msg := pb.Msg{}` later passed as `&msg`; weaker: `x := T{}` for a value
  filled in later.
- **skip:** `var x int = 0`, which revive reports; `i := 0` vs `var i int` and `&T{}` vs
  `new(T)` (non-decisions in google-decisions); empty slices (google-decisions:nil-slices).
- **example:** `coords := Point{X: 0, Y: 0}; json.Unmarshal(b, &coords)` -> `var coords Point`

### google-practices:vardeclzero/uncopyable — Declaring variables with zero values: uncopyable fields
- **meta:** severity=consider · scope=decl · check=lint+llm · lint=govet:copylocks · overlaps=google-decisions:copying
- **rule:** A field that must not be copied (a `sync.Mutex`, a `bytes.Buffer`) can be a value
  field that relies on its zero value instead of a pointer; the containing type is then
  passed around as a pointer and its methods take pointer receivers. Local variables of such
  composites may still be values.
- **look for:** `mu *sync.Mutex` fields allocated in constructors only to make copies safe;
  value receivers or by-value parameters of types holding a `bytes.Buffer` or similar
  (copylocks only sees lock types).
- **skip:** copies of types holding a mutex through value receivers, parameters, returns or
  assignments — govet copylocks reports them.
- **example:** `type Counter struct { mu *sync.Mutex }` -> `type Counter struct { mu sync.Mutex }` with `func (c *Counter) IncrementBy(...)`

### google-practices:vardeclcomposite — Composite literals
- **meta:** severity=should · scope=body · check=llm · custom=field-by-field-init · overlaps=google-decisions:literal-formatting
- **rule:** When you know the initial elements or members, declare the value with a
  composite literal (`Point{X: x, Y: y}`, `[]int{2, 3, 5}`, a map literal) instead of filling
  it in afterwards. Empty or memberless literals are visually noisier than a zero-value
  declaration. For a pointer to a zero value `new(T)` and `&T{}` are both fine; `new` hints
  that non-empty values come from a constructor or builder rather than a literal.
- **look for:** a zero value followed by consecutive assignments of known fields, map
  entries with constant keys, or `append`s of constants that one literal would express.
- **skip:** values filled conditionally or from intermediate results; the choice between
  `new(T)` and `&T{}`; empty map literals that are written to later.
- **example:** `var p Point; p.X = 1; p.Y = 2` -> `p := Point{X: 1, Y: 2}`

### google-practices:vardeclsize — Size hints
- **meta:** severity=consider · scope=body · check=llm
- **rule:** Size hints and preallocation (`make([]T, 0, n)`, `make(map[K]V, n)`) belong in
  performance-sensitive code backed by empirical analysis (benchmarks); most code needs none.
  Preallocating a known final size (map to slice conversion) is fine but not a readability
  requirement, and may not be worth the clutter in small cases. Over-allocating wastes memory
  and can hurt performance; when in doubt use a zero value or a composite literal.
- **look for:** large or magic capacities with no comment or benchmark behind them;
  capacities far above the realistic element count; preallocation clutter in small, cold code.
- **skip:** missing size hints are not a finding (prealloc reports are not violations of
  this guide); hints sized from the source (`len(src)`) in conversions; commented sizes.
- **example:** `q := make([]Node, 0, 1<<20)` with no rationale -> `var q []Node`, or a commented, measured size
- **note:** uber:prefer-specifying-container-capacity (prealloc) asks for capacity hints
  "where possible"; this guide treats them as optional, so the two pull in opposite directions.

### google-practices:decl-chan — Channel direction
- **meta:** severity=should · scope=body · check=llm · custom=chan-direction
- **rule:** Specify channel direction (`<-chan T`, `chan<- T`) where possible: the compiler
  then catches mistakes such as closing or sending on a channel the function should only
  read, and the type conveys who owns the channel.
- **look for:** parameters, results and struct fields of type `chan T` that the code only
  receives from (`<-ch`, `range`) or only sends to and closes.
- **skip:** channels the function both sends on and receives from, or passes to code that
  needs a bidirectional channel; the owner that creates the channel and hands out views.
- **example:** `func sum(values chan int) int` -> `func sum(values <-chan int) int`
