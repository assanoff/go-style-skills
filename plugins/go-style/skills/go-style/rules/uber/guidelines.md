# Uber Go Style Guide — Guidelines

Uber's core guidelines: interfaces and receivers, mutexes, copying slices and maps at API
boundaries, defer, channel sizes, enums, and modelling time with package `time`.

### uber:pointers-to-interfaces — Pointers to Interfaces
- **meta:** severity=should · scope=decl · check=lint+llm · lint=gocritic:ptrToRefParam · custom=ptr-to-interface · overlaps=google-decisions:pass-values
- **rule:** Pass interfaces as values; you almost never need a pointer to an interface. An
  interface value is already a type pointer plus a data pointer, and the data can itself be a
  pointer: store a pointer in the interface when its methods must modify the underlying data.
- **look for:** pointers to interfaces (`*io.Reader`, `*Store`) in struct fields and variables,
  and `&iface` passed around — ptrToRefParam checks only parameters and results.
- **skip:** out-parameters that must overwrite the caller's interface variable (an
  interface-typed `errors.As` target).
- **example:** `func process(r *io.Reader)` -> `func process(r io.Reader)`
- **note:** ptrToRefParam also flags pointers to maps and channels (google-decisions:pass-values
  covers those).

### uber:verify-interface-compliance — Verify Interface Compliance
- **meta:** severity=should · scope=decl · check=llm · conflicts=effective:blank_implements
- **rule:** Where appropriate, verify at compile time that a type implements an interface
  (`var _ http.Handler = (*Handler)(nil)`): for exported types whose API contract requires the
  interface, for types in a family implementing the same interface, and wherever breaking the
  interface would break users. The right-hand side is the zero value of the asserted type:
  `nil` for pointers, slices and maps, an empty literal (`LogHandler{}`) for structs.
- **look for:** exported handlers, middleware, codecs or plugin implementations with no
  assertion to catch a signature drift; assertions that allocate (`var _ I = &T{}`).
- **skip:** unexported one-off implementations that belong to no family of types.
- **example:** `type Handler struct{...}` alone -> add `var _ http.Handler = (*Handler)(nil)`
- **note:** Effective Go reserves these declarations for the rare types with no static
  conversion in the package and calls the others redundant; Uber applies them more broadly.
  Effective Go wins in multi-guide runs.

### uber:receivers-and-interfaces — Receivers and Interfaces
- **meta:** severity=consider · scope=body · check=llm · overlaps=google-decisions:receiver-type, effective:pointers_vs_values
- **rule:** Choose receivers knowing the method-set rules: value-receiver methods can be called
  on values and pointers, and both `T` and `*T` satisfy interfaces made of them;
  pointer-receiver methods need a pointer or an addressable value (map elements are not), and
  only `*T` satisfies the interface. Store pointers (`map[K]*T`) when callers need the pointer
  methods. The section is explanatory and points to Effective Go.
- **look for:** values kept in maps or slices and updated through copy-modify-write-back
  dances; pointer methods called on copies (range variables, values read out of a map) whose
  changes are silently lost.
- **skip:** misuse the compiler already rejects (pointer methods on map elements, a `T`
  assigned to an interface that needs `*T`).

### uber:zero-value-mutexes-are-valid/pointer — Zero-value Mutexes are Valid: no mutex pointers
- **meta:** severity=should · scope=body · check=llm · custom=mutex-pointer · overlaps=google-practices:vardeclzero, effective:allocation_new
- **rule:** The zero value of `sync.Mutex` and `sync.RWMutex` is valid, so you almost never need
  a pointer to a mutex: declare `var mu sync.Mutex`, and when a struct is used by pointer, make
  the mutex a non-pointer field of it.
- **look for:** fields or variables of type `*sync.Mutex`/`*sync.RWMutex`; `new(sync.Mutex)` or
  `&sync.RWMutex{}`, for instance in constructors.
- **skip:** one lock deliberately shared by several values.
- **example:** `mu := new(sync.Mutex)` -> `var mu sync.Mutex`

### uber:zero-value-mutexes-are-valid/embedding — Zero-value Mutexes are Valid: no embedded mutexes
- **meta:** severity=should · scope=decl · check=lint · lint=embeddedstructfieldcheck~(Mutex)
- **rule:** Do not embed a mutex in a struct, even an unexported one: embedding adds a `Mutex`
  field and `Lock`/`Unlock` to the type (for exported types, to its API). Use a named field
  such as `mu sync.Mutex` so the lock stays an implementation detail.
- **example:** `type SMap struct { sync.Mutex; data map[string]string }` ->
  `type SMap struct { mu sync.Mutex; data map[string]string }`

### uber:copy-slices-and-maps-at-boundaries/receiving — Copy Slices and Maps at Boundaries: receiving
- **meta:** severity=should · scope=body · check=llm · custom=slice-map-param-stored
- **rule:** Slices and maps share their underlying data, so if you keep a slice or map received
  as an argument, the caller can still modify it behind your back; store a copy.
- **look for:** setters and constructors assigning a caller's slice or map straight to a field
  or package variable (`d.trips = trips`), especially when it is later read, sorted or
  modified.
- **skip:** arguments only read during the call; documented ownership transfer.
- **example:** `d.trips = trips` -> `d.trips = slices.Clone(trips)` (or `make` plus `copy`)

### uber:copy-slices-and-maps-at-boundaries/returning — Copy Slices and Maps at Boundaries: returning
- **meta:** severity=should · scope=body · check=llm · custom=slice-map-field-returned
- **rule:** Likewise, don't return a slice or map that is internal state: callers can modify it,
  and data guarded by a mutex escapes the lock, inviting data races. Return a copy.
- **look for:** getters or `Snapshot()` methods returning `s.counters`/`c.items` directly,
  especially right after `mu.Lock(); defer mu.Unlock()`.
- **skip:** values built fresh for the caller and not kept on the receiver.
- **example:** `return s.counters` -> `return maps.Clone(s.counters)` (or a copy loop)

### uber:defer-to-clean-up — Defer to Clean Up
- **meta:** severity=should · scope=body · check=llm · custom=unlock-without-defer · overlaps=effective:defer
- **rule:** Use `defer` to clean up resources such as files and locks; releasing them by hand
  before each return is easy to miss. Defer's overhead is tiny: avoid it only if you can prove
  the function runs in nanoseconds. The readability win matters most in larger functions.
- **look for:** `Unlock()`/`Close()` repeated before several returns; a release only at the end
  of a function with early returns in between.
- **skip:** critical sections deliberately ended before slow work later in the function;
  acquisitions inside loops, where deferred calls would pile up until return.
- **example:** `p.Lock(); if c { p.Unlock(); return x }; ...; p.Unlock()` -> `p.Lock(); defer p.Unlock()`

### uber:channel-size-is-one-or-none — Channel Size is One or None
- **meta:** severity=should · scope=body · check=llm · custom=chan-buffer-size
- **rule:** Channels should usually be unbuffered or have a buffer of one. Any other size must
  get a high level of scrutiny: how is it determined, what prevents the channel from filling
  up under load and blocking writers, and what happens when it does?
- **look for:** magic buffer sizes (`make(chan T, 64)`, `1000`) with no reasoning; buffers that
  paper over a slow or missing receiver; producers with no plan for a full channel.
- **skip:** sizes with an evident bound: a semaphore sized to the concurrency limit, one slot
  per known sender (`make(chan error, len(tasks))`) so no send can block.
- **example:** `c := make(chan int, 64) // ought to be enough` -> `c := make(chan int, 1)` or `make(chan int)`

### uber:start-enums-at-one — Start Enums at One
- **meta:** severity=should · scope=decl · check=llm · custom=enum-iota-zero
- **rule:** Enums declared as a custom type with an `iota` const block should usually start at a
  non-zero value (`iota + 1`): variables default to 0, so an unset value would silently be a
  valid member. Start at zero when the zero value is the desirable default behavior.
- **look for:** typed `iota` blocks whose first constant (`= iota`) is an ordinary option such
  as `Add` or `Read`.
- **skip:** zero as the intended default (`LogToStdout`) or as an explicit unknown/unset member;
  bit flags (`1 << iota`).
- **example:** `Add Operation = iota` -> `Add Operation = iota + 1`

### uber:use-timetime-for-instants-of-time — Use `time.Time` for instants of time
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:time-equal
- **rule:** Represent instants as `time.Time` and use its methods to compare, add or subtract
  (`Before`, `After`, `Equal`, `Add`, `Sub`) instead of integer arithmetic, which bakes in
  false assumptions such as 24-hour days or 365-day years.
- **look for:** Unix-second or millisecond integers standing for instants in signatures,
  fields and comparisons; `86400`/`24*60*60` arithmetic on timestamps.
- **skip:** `==`/`!=` on `time.Time` (revive reports it); boundaries that cannot carry a
  `time.Time` (external-systems rule).
- **example:** `func isActive(now, start, stop int) bool` -> `func isActive(now, start, stop time.Time) bool`

### uber:use-timeduration-for-periods-of-time/type — Use `time.Duration` for periods of time
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:time-naming · custom=int-duration-param
- **rule:** Represent periods as `time.Duration`, not integers, so the unit is unambiguous:
  `poll(10*time.Second)`, not `poll(10)` (seconds or milliseconds?).
- **look for:** integer parameters or fields such as `delay`, `timeout`, `interval` or `ttl`,
  later converted with `time.Duration(x) * time.Millisecond`.
- **skip:** `Duration` variables with unit suffixes (`timeoutSecs`) — revive reports them;
  formats that cannot carry a Duration (external-systems rule).
- **example:** `func poll(delay int)` -> `func poll(delay time.Duration)`

### uber:use-timeduration-for-periods-of-time/calendar-days — Use `time.Duration` for periods of time: Add vs AddDate
- **meta:** severity=should · scope=body · check=llm
- **rule:** When moving an instant, pick the method by intent: `Time.AddDate` for the same time
  of day on the next calendar day, `Time.Add` for an instant exactly 24 hours later — a day
  does not always have 24 hours.
- **look for:** `t.Add(24 * time.Hour)` (or `n*24*time.Hour`, `7*24*time.Hour`) used for
  "tomorrow", "in n days", daily schedules or date boundaries.
- **skip:** fixed-length intervals such as TTLs, timeouts or rate windows, where exactly 24
  hours is meant.
- **example:** `next := t.Add(24 * time.Hour) // same time tomorrow` -> `next := t.AddDate(0, 0, 1)`

### uber:use-timetime-and-timeduration-with-external-systems — Use `time.Time` and `time.Duration` with external systems
- **meta:** severity=should · scope=decl · check=llm
- **rule:** Use `time.Duration` and `time.Time` when talking to external systems where possible:
  command-line flags (`flag.Duration`), JSON (`time.Time` as RFC 3339), SQL (`DATETIME` and
  `TIMESTAMP` columns, if the driver supports it), YAML. If a Duration can't be used, use
  `int` or `float64` with the unit in the field name; if a `time.Time` can't, use a `string`
  formatted as RFC 3339 unless another format is agreed upon.
- **look for:** config or API struct fields such as `Interval int` or `Timeout int64` with no
  unit in the name; `flag.Int("timeout", ...)`; epoch integers or ad-hoc timestamp strings in
  JSON or YAML payloads.
- **skip:** fields whose name and type are dictated by an external schema.
- **example:** `` Interval int `json:"interval"` `` -> `` IntervalMillis int `json:"intervalMillis"` ``
- **note:** `encoding/json` has no Duration support (it would emit nanoseconds), hence the
  unit-suffix fallback; the `time` package ignores leap seconds.
