# Uber Go Style Guide — Patterns

The Patterns and Linting sections of the Uber guide cover table-driven and parallel
tests, functional options, and the recommended lint setup.

### uber:test-tables — Test Tables
- **meta:** severity=should · scope=test · check=llm · overlaps=google-decisions:table-driven-tests
- **rule:** When the code under test must be checked against multiple conditions where
  parts of the inputs and outputs change, use a table-driven test with subtests instead
  of repeating the test logic; tables make it easier to add cases, add context to
  failure messages and avoid duplicated logic.
- **look for:** one test repeating the same call-and-assert block with different
  literals; several `Test…` functions that differ only in their inputs.
- **skip:** cases that need different logic (see
  uber:avoid-unnecessary-complexity-in-table-tests).
- **note:** Uber's examples use testify `require`/`assert`, but the rule does not ask for
  an assertion library; in multi-guide runs google-decisions:assert governs that choice.

### uber:test-tables/naming — Test table naming
- **meta:** severity=consider · scope=test · check=llm
- **rule:** By Uber's convention the slice of cases is named `tests`, each case `tt`, and
  case fields use `give` and `want` prefixes for inputs and expected outputs.
- **look for:** new tables named `cases`/`testCases`, loop variables `tc`/`test`, fields
  such as `input`/`expected`.
- **skip:** test files that consistently follow another convention (uber:be-consistent).
- **example:** `for _, tc := range cases { … tc.input … tc.expected }` -> `for _, tt := range tests { … tt.give … tt.want }`

### uber:avoid-unnecessary-complexity-in-table-tests — Avoid Unnecessary Complexity in Table Tests
- **meta:** severity=should · scope=test · check=llm · custom=table-test-branching · overlaps=google-decisions:table-driven-tests,google-decisions:table-tests-data-driven
- **rule:** Do not use a table test when subtests need complex or conditional logic inside
  the loop — such tests are hard to read, debug and maintain; split it into several
  tables or separate `Test…` functions. Aim for the narrowest unit of behavior, shallow
  tests without conditional assertions, every table field used in every case, and all
  test logic run for every case.
- **look for:** table fields like `shouldCallX`/`expectCall` next to `wantErr`; several
  `if tt.…` branches configuring mocks; function-valued fields
  (`setupMocks func(*FooMock)`); fields used by only some rows.
- **skip:** a single success/failure branch on `wantErr`/`shouldErr` in a short,
  straightforward body; grouping cases whose behavior differs only by input.
- **example:** one table with `shouldCallX`/`shouldCallY` and conditional mock setup -> `TestShouldCallX`, `TestShouldCallYAndFail`

### uber:parallel-tests — Parallel Tests
- **meta:** severity=must · scope=test · check=lint · lint=govet:loopclosure
- **rule:** Parallel subtests, like loops that spawn goroutines or capture references,
  must explicitly assign the loop variable inside the loop's scope so each iteration
  sees the expected value.
- **skip:** modules declaring `go 1.22` or later, where loop variables are per-iteration.
- **note:** obsolete since Go 1.22: modernize's forvar reports `tt := tt` as unneeded, and
  govet's loopclosure reports captures only for older language versions. The guide
  still asks for the copy although its example no longer shows it.

### uber:functional-options — Functional Options
- **meta:** severity=consider · scope=decl · check=lint+llm · lint=revive:argument-limit · overlaps=google-practices:variadic-options
- **rule:** For optional arguments of constructors and other public APIs you expect to
  grow, especially with three or more parameters, accept variadic `...Option` values.
  Uber suggests an `Option` interface with an unexported `apply(*options)` method over
  closures: such options can be compared in tests and mocks and can implement
  `fmt.Stringer`.
- **look for:** exported constructors whose optional parameters callers fill with
  defaults (`db.Open(addr, db.DefaultCache, zap.NewNop())`); new optional parameters
  appended to public signatures.
- **skip:** required parameters (keep them positional); unexported functions.
- **note:** argument-limit fires only above the configured maximum (6), well beyond
  Uber's three-parameter hint. Google's variadic-options example uses closures.

### uber:linting — Linting
- **meta:** severity=should · scope=repo · check=lint+llm · lint=errcheck
- **rule:** Lint consistently across the codebase, which matters more than any blessed
  linter set. At minimum run errcheck (errors are handled), goimports, revive (successor
  of the deprecated golint), govet and staticcheck, preferably through golangci-lint,
  and add linters that suit the project.
- **look for:** no golangci-lint config or CI lint step; a config missing part of that
  base set; packages or directories excluded from linting.
- **skip:** extra linters beyond the base set (encouraged).
- **note:** errcheck findings map here because this is where Uber asks for errors to be
  handled; findings of the other base linters map to the specific rules.
