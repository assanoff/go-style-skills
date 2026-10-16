# Effective Go — Concurrency and Errors

Effective Go on sharing memory by communicating, goroutines, channels and
parallelism, and on reporting errors, panicking and recovering.

### effective:sharing — Share by communicating
- **meta:** severity=consider · scope=body · check=llm
- **rule:** Do not communicate by sharing memory; instead, share memory by
  communicating: pass values between goroutines on channels so only one goroutine
  has access at a time, instead of coordinating access to shared variables. Don't
  take it too far — a reference count, for instance, may be best done with a mutex
  around an integer.
- **look for:** intricate locking around state that one owning goroutine could serve
  through channel requests; a goroutine still touching a value after sending it on
  a channel; variables shared between goroutines with no synchronization.
- **skip:** small shared state such as counters or flags behind a mutex or atomics.

### effective:goroutines — Goroutines
- **meta:** severity=consider · scope=body · check=llm · overlaps=google-decisions:goroutine-lifetimes
- **rule:** A `go` statement runs a call concurrently, and the goroutine exits silently
  when the call completes, so a goroutine whose completion or result matters needs a
  way to signal it, such as a channel. A function literal launched with `go` must be
  called (`go func() { ... }()`); it is a closure, and the variables it refers to
  survive as long as it needs them.
- **look for:** goroutines whose completion, result or error the launching code relies
  on without receiving any signal; closures sharing a variable that the launching
  code keeps modifying.
- **note:** Before Go 1.22 loop variables were shared across iterations, so closures
  started in a loop needed a per-iteration copy. `sync.WaitGroup.Go` (Go 1.25) and
  `errgroup` are common completion signals.

### effective:channels — Channels
- **meta:** severity=should · scope=body · check=llm
- **rule:** An unbuffered channel combines communication with synchronization; a
  buffered channel can act as a semaphore that limits throughput. Bound concurrency
  where goroutines are created: acquire the semaphore before starting each
  goroutine, or start a fixed number of workers that range over the request channel.
  Spawning a goroutine per request that then waits on the semaphore can consume
  unlimited resources when requests arrive too fast.
- **look for:** `for { req := <-queue; go handle(req) }` where `handle` takes the
  semaphore inside; one goroutine per item of an unbounded input with no limit.
- **note:** The guide's gated loop (`go func() { process(req); <-sem }()` inside
  `for req := range queue`) was buggy before Go 1.22 because `req` was shared.
  `errgroup.Group.SetLimit` and `golang.org/x/sync/semaphore` package the same bound.

### effective:parallel — Parallelization
- **meta:** severity=should · scope=body · check=llm · custom=numcpu-sizing
- **rule:** Independent pieces of a CPU-bound calculation can run in parallel, one per
  CPU, each signalling completion on a channel. Size that parallelism with
  `runtime.GOMAXPROCS(0)`, which honors the user's resource request, rather than a
  hard-coded core count or `runtime.NumCPU()`. Concurrency (structuring a program as
  independent components) is not parallelism (running calculations simultaneously),
  and not every parallel problem fits Go's model.
- **look for:** constants such as `numCPU = 4` or fixed worker counts for CPU-bound
  fan-out; `runtime.NumCPU()` sizing worker pools.
- **skip:** pool sizes set by I/O limits or external quotas rather than CPUs.
- **note:** Since Go 1.25 the default `GOMAXPROCS` also follows container CPU limits
  (cgroup quota), so `NumCPU` can overstate the CPUs actually available.

### effective:errors — Errors
- **meta:** severity=should · scope=body · check=llm · overlaps=google-practices:error-extra-info,google-practices:error-structure
- **rule:** Return an `error` describing what went wrong, not just a nil result. Detailed
  errors carry context — `os.PathError` holds the operation, the path and the
  underlying error ("open /etc/passwx: no such file or directory") — so they stay
  useful far from the call. When feasible, error strings identify their origin with a
  prefix naming the operation or package ("image: unknown format"). Callers that
  care about details inspect the error's type and fields.
- **look for:** messages lacking the failing operation or input ("invalid value");
  custom error types that drop the underlying error; package errors whose text has
  no package or operation prefix.
- **skip:** context the underlying error already carries (os errors include the path).
- **note:** Predates Go 1.13: inspect with `errors.As`/`errors.Is` (or `errors.AsType`,
  Go 1.26) instead of a direct type assertion or `==`, so wrapped (`%w`) errors match.

### effective:panic — Panic
- **meta:** severity=should · scope=body · check=llm · overlaps=google-decisions:dont-panic,google-practices:checks-and-panics
- **rule:** Report errors to the caller with an extra `error` result. `panic` is for
  unrecoverable situations where the program cannot continue, or to flag something
  impossible. Real library functions should avoid it: if the problem can be masked
  or worked around, keep running rather than take down the whole program. A possible
  exception is initialization — a library that truly cannot set itself up may panic.
- **look for:** `panic` on invalid input, I/O or other recoverable failures in library
  code where an error result could be returned.
- **skip:** panics in `init` or package setup that cannot proceed; panics marking
  genuinely impossible states.

### effective:recover — Recover
- **meta:** severity=should · scope=body · check=lint+llm · lint=revive:defer~recover must be called · overlaps=google-practices:when-to-panic · conflicts=uber:dont-panic/production
- **rule:** `recover` stops the unwinding only when called directly by a deferred
  function; anywhere else it returns nil. A package may use panic and recover to
  simplify its internal error handling (e.g. a parser), but must turn panics into
  returned errors at its boundary — never exposing them to clients — and recover only
  its own panic type, so unexpected run-time errors keep unwinding.
- **look for:** exported functions that let internal panics escape; recover handlers
  converting any panic value into an error without checking its type; `recover()`
  in a helper called by the deferred function, where it returns nil.
- **skip:** `recover()` outside deferred code and `defer recover()` — revive `defer`
  reports them (it also flags a named function that is itself deferred, which works).
- **note:** Effective Go also recovers per server goroutine to log failures without
  killing the others; Google best practices (higher priority) advise against that.
