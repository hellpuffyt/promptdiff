# Production readiness — promptdiff

Audit date: 2026-10-22. Tested code commit: `2031583` (branch
`audit/production-readiness`); later commits change documentation and
repository metadata only.

## Scope

Regression harness for prompt changes: a YAML/JSON suite of cases with nine
deterministic, model-free assertion types; a `Runner` protocol with the
shipped `ReplayRunner` (recorded fixtures); `run` and `compare` subcommands
reporting per-assertion regressions/improvements and pass-rate deltas, as a
table or JSON, with CI exit codes. promptdiff never calls a model.

## Platforms and prerequisites

Python ≥ 3.10; runtime deps PyYAML 6.0.3, jsonschema 4.26.0 (tested).
Verified on macOS 27 (Apple Silicon), Python 3.12 (full + clean clone),
3.10 and 3.13 (suite). Not on PyPI (the PyPI name belongs to an unrelated
project). Linux/Windows CI legs not run for this audit. No API keys or
network needed; **no real LLM calls were made at any point** — tests use
`ReplayRunner` and deterministic fakes labelled as such, and a test-suite
network guard enforces it.

## Clean-clone verification

```bash
git clone -b audit/production-readiness <repo> promptdiff && cd promptdiff
python3.12 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"     # exit 0
.venv/bin/promptdiff run --suite examples/suite.yaml --fixtures examples/fixtures --version v1
#   "4/5 cases passed (80%)", exit 1 (as README)
.venv/bin/promptdiff compare --suite examples/suite.yaml --fixtures examples/fixtures --base v1 --head v2
#   matches README: 80% -> 40%, 3 regressions, 1 improvement; exit 1
... --allow-regression --format json --text-diff                             # exit 0
.venv/bin/python -m pytest -q        # 153 passed
ruff check . ; mypy                  # clean; no issues in 9 files
```

## Commands and outcomes

| Step | Command | Exit | Result |
|---|---|---:|---|
| Baseline (main `0ce0230`) | `python -m pytest -q` | 0 | 140 passed, 0 failed, 0 skipped |
| Baseline lint/types | `ruff check .`, `mypy` | 0, 0 | clean |
| Final (3.10, 3.12, 3.13) | `python -m pytest -q` | 0 | 153 passed, 0 failed, 0 skipped |
| New tests on original code | `PYTHONPATH=<main>/src pytest tests/test_audit_regressions.py` | 2 | collection error (`FixtureError` did not exist); behaviour reproduced manually: `../../outside/leak` was read |
| Dependency audit | `uvx pip-audit … --strict -s osv` | 0 | no known vulnerabilities |
| Secret scan (tree + history) | detect-secrets; credential-pattern `git grep` | – | none |

CI: default branch `main`: **success** (`0ce0230`). Audit branch: pending
until pushed.

## Bugs found and fixed

| # | Severity | Defect | Regression test |
|---|---|---|---|
| 1 | Medium (path traversal) | Case ids / versions with `../` or absolute paths read files outside the fixtures directory into reports (`--format json`, `--text-diff`) | `test_case_id_cannot_escape_*`, `test_version_cannot_escape_*`, `test_cli_reports_escape_attempt_as_usage_error` |
| 2 | Low (doc/behaviour mismatch) | Invalid `matches_regex` pattern/flags only detected once a fixture existed; README promised a load-time error | `test_invalid_regex_is_rejected_when_the_suite_loads` |
| 3 | Low | Non-UTF-8 fixture → traceback | `test_non_utf8_fixture_is_a_clean_error` |
| 4 | Low (docs) | Windows-first install/test commands; no warning about the unrelated PyPI package | README |

## Security review

`yaml.safe_load` only; no network or subprocess in `src/`; fixture reads
contained to the fixtures directory; suite regexes run in Python `re`
(suite files must be reviewed like code). CI already had
`permissions: contents: read`.

## Known limitations

Assertions are lexical/structural only (no semantic judgement, by design);
symlinked fixture directories and symlinked fixture files pointing outside
the fixtures root are refused.

## Acceptance checklist

| Item | Expected | Command / test | Result | Actual | Reference |
|---|---|---|---|---|---|
| A1 | Install from source | README | pass | exit 0 | clean clone |
| A2 | Nine assertion types fire / don't fire | tests | pass | yes | `test_assertions.py` |
| A3 | Compare reports regressions/improvements exactly | tests + example | pass | 3 / 1, README match | `test_compare.py` |
| A4 | Exit codes 0/1/2, `--allow-regression` | tests + clean clone | pass | yes | `test_cli.py` |
| A5 | No real model/network in tests | network guard | pass | guard active | `tests/conftest.py` |
| A6 | Fixture reads contained | tests | pass | refused | `test_audit_regressions.py` |
| A7 | Invalid suites rejected at load | tests | pass | yes | `test_suite.py`, regressions |

## Classification proposal

**Partially Verified** — documented behaviour tested offline on macOS with
Python 3.10–3.13, clean clone passes. Not verified: Linux/Windows CI on the
audit branch (pending push); any live-provider `Runner` (out of scope by
design).
