# Uber Go Style Guide — Performance

Uber's performance guidelines; the guide applies them only to hot paths.

### uber:prefer-strconv-over-fmt — Prefer strconv over fmt
- **meta:** severity=consider · scope=body · check=lint+llm · lint=perfsprint~strconv|hex\.Encode
- **rule:** On hot paths, convert primitives to and from strings with `strconv` rather than
  `fmt`: it is faster and allocates less (64 ns and 1 alloc vs 143 ns and 2 allocs per call in
  the guide's benchmark).
- **look for:** single-value parsing with `fmt.Sscan`/`fmt.Sscanf` (use `strconv.Atoi`,
  `ParseInt`, `ParseFloat`, `ParseBool`) and float formatting with `fmt` in hot loops —
  perfsprint only covers integer, bool and hex formatting.
- **skip:** code off the hot path; multi-part messages where `fmt.Sprintf` reads better.
- **example:** `s := fmt.Sprint(rand.Int())` -> `s := strconv.Itoa(rand.Int())`

### uber:avoid-repeated-string-to-byte-conversions — Avoid repeated string-to-byte conversions
- **meta:** severity=consider · scope=body · check=llm · custom=loop-const-byte-conversion
- **rule:** Don't create byte slices from a fixed string repeatedly; convert once and reuse the
  result (22 ns vs 3 ns per operation in the guide's benchmark).
- **look for:** `[]byte("literal")` or a conversion of a loop-invariant string inside loops or
  per-request hot code.
- **skip:** code off the hot path; callees that modify or retain the slice, where sharing one
  slice would be a bug.
- **example:** `for ... { w.Write([]byte("Hello world")) }` -> `data := []byte("Hello world")` before the loop, `w.Write(data)` inside

### uber:specifying-map-capacity-hints — Specifying Map Capacity Hints
- **meta:** severity=consider · scope=body · check=llm · custom=map-capacity-hint · conflicts=google-practices:vardeclsize
- **rule:** Where possible, give `make` a capacity hint for maps whose size is known up front
  (`make(map[K]V, len(src))`) so they grow and allocate less. The hint only approximates the
  buckets needed, so allocations may still happen before it is reached.
- **look for:** `make(map[K]V)` or `map[K]V{}` filled in a loop over a collection of known
  length.
- **skip:** code off the hot path; fills whose final size is unknown or much smaller
  (filtered); tiny maps.
- **example:** `m := make(map[string]os.DirEntry)` -> `m := make(map[string]os.DirEntry, len(files))`
- **note:** Google's best practices say most code needs no size hints and want empirical
  evidence for them; Google's guidance wins in multi-guide runs.

### uber:specifying-slice-capacity — Specifying Slice Capacity
- **meta:** severity=consider · scope=body · check=lint+llm · lint=prealloc · conflicts=google-practices:vardeclsize
- **rule:** Where possible, give `make` a capacity for slices, particularly ones you append to
  (`make([]T, 0, n)`): unlike a map hint, slice capacity is allocated up front, so appends
  don't reallocate until the length reaches it.
- **look for:** `make([]T, 0)` or `var s []T` appended to in counted `for i := 0; i < n; i++`
  loops or in loops with `break`/`continue`/`return` — prealloc skips those by default.
- **skip:** code off the hot path; unknown final sizes; range loops prealloc already reports.
- **example:** `data := make([]int, 0)` -> `data := make([]int, 0, size)`
- **note:** Google's best practices treat preallocation as optional outside measured hot code;
  Google's guidance wins in multi-guide runs.
