# Contributing

Thanks for considering a contribution to promptdiff.

## Development setup

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# or: .venv/bin/python -m pip install -e ".[dev]"        # macOS/Linux
```

## Gates

All of these must pass before a change is merged. They also run in CI on
Python 3.10-3.13 across Linux, Windows, and macOS.

```bash
pytest
ruff check .
mypy
```

Please add or update tests for any behavioural change -- promptdiff is a
testing tool, so its own test suite should model good practice.

## Adding a new assertion type

1. Add a frozen dataclass to `src/promptdiff/assertions.py` implementing
   `describe()` and `check()`, with a `type: ClassVar[str]` name.
2. Register it in `_REGISTRY` and, if it has required fields, in
   `_REQUIRED_FIELDS`.
3. Document it in the README's "Suite format" section.
4. Add tests covering both a passing and a failing case, plus any
   suite-parsing error paths (missing fields, wrong types).

## Reporting issues

Please include the suite/assertion snippet that reproduces the problem
and the exact command you ran. Since promptdiff has no network
dependency at runtime, issues should be reproducible entirely offline.

## Code style

- No stub or placeholder implementations -- every documented flag and
  assertion type must actually work.
- Keep the tool fully offline: no network calls, no API keys, ever, in
  the library or the CLI.
- Prefer explicit, typed dataclasses over loosely-typed dicts for
  anything that crosses a function boundary.

## Commit and PR expectations

- Keep commits focused; explain the "why" in the message body when it
  isn't obvious from the diff.
- Update `CHANGELOG.md` under an "Unreleased" heading for user-facing
  changes.
