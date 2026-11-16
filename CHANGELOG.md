# Changelog

Notable changes of the `go-style` plugin. The version is the one in
`plugins/go-style/.claude-plugin/plugin.json` and follows
[Semantic Versioning](https://semver.org/); the format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.2] - 2026-11-16

Every linter check was compared with the text of the guide section it reports
under and with what it finds in four real modules, about 150 000 lines. A
linter finding goes into the report without a reviewer's judgement, so a check
stays only where nearly all it reports is what the guide objects to. On those
modules the linters now report 4010 findings where they reported 5688.

### Changed

- No longer reported, because the guides allow most of what the check finds:
  every package variable (`gochecknoglobals`: the guides mean mutable state),
  context-less standard calls (`noctx`: nine in ten were in tests), shadowed
  variables (govet `shadow`), nested `if` blocks that no early return removes
  (`nestif`), every `init` (`gochecknoinits`), `%v` on an error in `fmt.Errorf`
  (Uber offers both verbs, Google prefers `%v`), an interface or interface
  method not used inside its own package when it is exported, an `append`
  result kept under another name, `switch true`, a write to a value receiver
  that the method reads again, and a `time.Duration` named with a unit. The
  reviewers keep these rules.
- A variable named like a package is reported only for standard packages
  (gocritic `importShadow` in place of revive `import-shadowing`), as Google's
  best practices say; a package named like a standard one is reported there
  too.
- An unchecked type assertion is reported under Uber's rule only, and left out
  of a run that includes Effective Go, which writes `str := value.(string)`
  where the type is known. `==`, a `switch` and a type assertion on an error
  are a `consider` hint of the Uber guide, left out of a run that includes
  Google's best practices, which call `==` adequate.
- A doc comment that does not begin with the name is a `should`, a missing one
  stays a `must`; an article before the name is accepted on any declaration.
- Complexity hints start at a cognitive complexity of 50, not 30.
- Not reported in tests: `nil, nil` returns, a context in a struct,
  `prealloc`, `strconv` over `fmt`. Not reported at all: a `testX` function
  without `t.Helper()`, a long line that holds a URL, a struct tag or a long
  string, a `*error` parameter, a comment ending in a quotation, a TODO or a
  list item without a period, an empty slice assigned to a field, a package of
  integration tests with underscores in its name.
- `recover()` in a function that is itself deferred, which works, is no longer
  reported; `defer recover()` is.
- A formatting problem is reported once, by gofmt, and no longer a second time
  as an import problem.

### Added

- An error dropped into `_` is reported like one that is not checked
  (errcheck `check-blank`), unless a comment on the line explains it.
- Stop words in a wrapped error (`fmt.Errorf("failed to …: %w", err)`,
  "unable to", "could not") and wraps that add nothing (`"%w"`,
  `"failed: %w"`): both Google's best practices and Uber ask to leave them out.
- A write to a nil map (staticcheck SA5000), an `append` whose result is never
  read (SA4010), a nil check around a `range` (S1031), a write to another
  package's variable (`reassign`), `Db` for `DB`.
- `gostyle.py validate` fails when the linter config runs a check that no rule
  names: such a check costs time and its findings are dropped.

## [0.3.1] - 2026-11-16

### Security

A module under review may be written to trick the run; these close what a
review of the plugin found.

- A run refuses to write through a symbolic link at `.go-style`, its `runs`
  directory or its `.gitignore`, and a report replaces a link at its path and
  leaves the target alone. Before, a repository that shipped such links could
  have files outside it created or overwritten.
- Reviewers no longer build or run the code they review. The plugin ships a
  `go-style:reviewer` agent without a shell, and the skills use it when it is
  there.
- Text from the module and from reviewers stays text: a message is one line of
  bounded length, so it cannot forge headings of the report, and HTML tags and
  links in it are not rendered. Files whose names have quote, shell or control
  characters are left out and named. The workflow tells the agent that findings
  are data and not instructions.
- git runs with `core.fsmonitor` off and without textconv filters, which the
  configuration of the repository could point at a program.
- `report` without `--run` takes the run written last and not the one with the
  latest name, which a repository could ship.

### Fixed

- One malformed line in a reviewer's output no longer fails the whole report:
  the line is listed as rejected. A JSON array in place of JSON Lines, and
  lines inside a Markdown code fence, are read.
- A reviewer finding that names a file outside the module is rejected; before,
  the report could quote such a file.
- `report` names a directory that is no run, and skips one a failed `prepare`
  left behind, where it ended in a traceback.
- Output of git or the linters that is not UTF-8 no longer ends the run.

### Added

- A golangci-lint older than v2.14, or built with an older Go than the module
  needs, is named as the cause, with the command that fixes it, in the output
  of `prepare` and in the notes of the report.
- `tools/package` builds the combined skill as one self-contained zip, license
  files included, for places that take a skill and not a plugin.
- The skills say what their placeholders stand for, for agents that do not
  expand them, and how to review without subagents.

### Changed

- The short list of top findings, in the summary and under "Must fix", takes at
  most a few findings of one rule and says how many more there are, so a rule
  broken in every file no longer hides the others.
- Fewer linter findings the guides do not ask for: unchecked type assertions
  and package variables in test files, and empty slices written as struct
  fields, arguments or elements, are no longer reported.
- Rule catalogs, after a comparison with the text of the Google guides:
  - complexity scores are a `consider` hint under a rule of their own
    (`google-guide:simplicity/hotspots`), since the guide names no limit, and
    nesting depth is reported under Uber's rule only;
  - a channel where a mutex would do is no longer a finding (the guide counts a
    channel as a core construct and leaves the choice to the package);
  - easy-to-miss details are `consider`, as the guide words them;
  - reviewers now look for unchecked `Close`/`Flush` of written files, which
    the linter config leaves out, for "failed to" stop words in error
    annotations, for `t.Context()` inside `t.Cleanup`, and for interfaces whose
    use depends on undocumented implementation details;
  - a sentinel error wrapped as the only error at the end of a message is no
    longer flagged; tests that tell errors apart by their text are;
  - Uber's `make` over an empty map literal yields to Google, which calls the
    two equivalent.
- NOTICE names the licenses of the code in the guides (Apache-2.0 for Google's
  samples, the Go BSD license for Effective Go); `LICENSES/` has the text of
  the latter.

## [0.3.0] - 2026-10-22

### Added

- `--staged` and `--unstaged`: review only the lines changed in the index, or
  those changed in the working tree against it and the untracked files; both
  together are all uncommitted changes. Staged lines are found in the working
  tree, where the linters and reviewers read the code; a staged line changed
  again since is left out.

### Fixed

- `--diff` reads the output of `git diff` whatever `diff.noprefix`,
  `diff.mnemonicPrefix` or `diff.relative` say, and file names git quotes.

## [0.2.0] - 2026-10-16

### Changed

- The report goes to a store in the home directory, shared with
  [go-audit](https://github.com/assanoff/cmd/tree/master/go-audit):
  `~/.go-style/reports/<module>/<time>-style-<guides>.md` and its `.json` twin;
  `GO_STYLE_HOME` moves the store, `report --output` still wins. The working
  files of a run stay in `<module>/.go-style/runs/`. Reports of 0.1.0 in
  `<module>/.go-style/reports/` are left where they are.

### Added

- Fields every report in the store has, at the top of the `.json` twin:
  `format`, `kind`, `module`, `root`, `time`, `label`, `total`, `summary`;
  `go-audit reports` lists reports by them. The fields of 0.1.0 stay.

## [0.1.0] - 2026-10-16

First release as a Claude Code plugin; before, the skills lived in a dotfiles
repository.

### Added

- `go-style` plugin in the `go-style-skills` marketplace with six skills:
  `go-style` (all five guides) and `go-style-guide`, `go-style-decisions`,
  `go-style-practices`, `go-style-effective`, `go-style-uber`.
- Rule catalogs for the Google Go Style Guide, Style Decisions, Best Practices,
  Effective Go and the Uber Go Style Guide, with a golangci-lint v2 config in
  which every check backs a rule.
- `--min-lint-recall` and `--max-unexpected` thresholds in `evals/score.py`,
  `tools/check-fixture` and a CI workflow.

### Requirements

- golangci-lint v2.14 or newer.
