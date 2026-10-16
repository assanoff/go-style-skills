# Changelog

Notable changes of the `go-style` plugin. The version is the one in
`plugins/go-style/.claude-plugin/plugin.json` and follows
[Semantic Versioning](https://semver.org/); the format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
