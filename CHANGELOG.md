# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-30

### Added

- Suite format (YAML/JSON) for describing fixed evaluation cases.
- Model-free assertions: `contains`, `not_contains`, `matches_regex`,
  `is_valid_json`, `json_has_keys`, `json_schema`, `max_length`,
  `starts_with`, `one_of`.
- Pluggable `Runner` interface and a `ReplayRunner` that replays recorded
  fixtures from disk, so the tool runs fully offline with no API keys.
- `promptdiff run` to run a suite against a single prompt version.
- `promptdiff compare` to compare a suite's behaviour across two prompt
  versions: per-assertion pass/fail transitions, aggregate pass-rate
  delta, and an optional unified text diff for human inspection.
  Exits non-zero on regression; `--allow-regression` overrides.
- Human table and JSON output formats for both subcommands.
- Example suite and fixtures under `examples/`.
