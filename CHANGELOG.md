# Changelog

Notable changes of the `go-style` plugin. The version is the one in
`plugins/go-style/.claude-plugin/plugin.json` and follows
[Semantic Versioning](https://semver.org/); the format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
