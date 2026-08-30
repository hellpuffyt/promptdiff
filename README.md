# promptdiff

A regression harness for prompt changes. Run a fixed evaluation suite
across two prompt versions and get a report of the **behavioural** delta
between them -- which cases changed verdict, which assertions newly
fail, and the aggregate pass-rate change -- instead of just a text diff
of raw outputs.

## What

promptdiff gives prompts the thing code already has: a fixture suite, a
diff of behaviour rather than text, and a pass/fail gate you can wire
into CI. You write a suite of cases (an input plus a list of assertions
the output must satisfy), record the outputs your prompt produces for
each version you want to compare, and promptdiff tells you exactly which
assertions flipped between versions.

## Why

Changing a system prompt is a code change with no test suite. Someone
edits the wording, ships it, and three days later discovers it broke
JSON output on 8% of inputs, or the assistant stopped refusing a class
of request it used to refuse. A text diff of the prompt tells you
nothing about that. promptdiff runs the same fixed suite through both
versions and reports the assertions that actually changed pass/fail
status -- the thing you actually care about.

## What this tool does not do

promptdiff makes no semantic judgement about your outputs. It does not
call a model to grade "is this a good answer," it does not do fuzzy
similarity scoring, and it never claims two outputs are "the same
meaning." Every assertion it ships is a deterministic, model-free check:
substring/regex matching, JSON validity and structure, length, and
membership in an allowed set. If a prompt's wording changes completely
but every assertion still passes, promptdiff reports "unchanged" --
correctly, because that is all it can know. If you need semantic
grading, layer an LLM-judge assertion on top by writing your own
`Runner` and assertion; promptdiff's job is the deterministic floor
under that, not a replacement for it.

## Features

- **Suite format** (YAML or JSON): a fixed list of cases, each with an
  input and a list of assertions.
- **Nine model-free assertion types**: `contains`, `not_contains`,
  `matches_regex`, `is_valid_json`, `json_has_keys`, `json_schema`,
  `max_length`, `starts_with`, `one_of`.
- **Pluggable runner interface**: promptdiff never calls a model. A
  `Runner` is anything with a `run(case_id, input_text) -> str` method.
- **`ReplayRunner` shipped out of the box**: reads pre-recorded outputs
  from a fixtures directory, so the whole tool -- including its own test
  suite -- runs fully offline, with zero API keys and zero network
  access.
- **Behavioural comparison**: `promptdiff compare` runs a suite through
  two versions and reports, per case and per assertion, whether it
  regressed, improved, or stayed the same -- plus the aggregate pass-rate
  delta.
- **Optional text diff**: `--text-diff` includes a unified diff of raw
  outputs for human inspection. It is never used to decide pass/fail.
- **CI-friendly exit codes**: non-zero on regression by default;
  `--allow-regression` to override deliberately.
- **Human table or JSON output** for both subcommands.

## Architecture

```
src/promptdiff/
  assertions.py   model-free assertion types + suite-level parsing of them
  suite.py        suite file parsing/validation (YAML or JSON) -> Suite/Case
  runner.py       Runner protocol + ReplayRunner (fixture-backed, offline)
  evaluate.py      run a Suite through one Runner -> CaseResult per case
  compare.py      run a Suite through two Runners, pair up results,
                   compute per-assertion transitions and pass-rate deltas
  report.py       render run/compare results as a table or JSON
  cli.py          argparse CLI: `promptdiff run`, `promptdiff compare`
```

Data flows one direction: `suite.py` builds a `Suite` of `Case` objects,
each holding parsed `Assertion` instances from `assertions.py`.
`evaluate.py` feeds each case's input through a `Runner` and checks the
output against that case's assertions, producing a `CaseResult`.
`compare.py` runs that twice (base and head) and pairs the two
`CaseResult` sequences up case-by-case and assertion-by-assertion into
`AssertionTransition`s, which is where "regression" and "improvement"
are defined. Nothing here calls a network or a model; the only IO is
reading the suite file and the fixture files.

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/hellpuffyt/promptdiff.git
cd promptdiff
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# or: .venv/bin/python -m pip install -e ".[dev]"        # macOS/Linux
```

This installs the `promptdiff` console script inside the virtual
environment.

## Usage

### Run a suite against one version

```bash
promptdiff run \
  --suite examples/suite.yaml \
  --fixtures examples/fixtures \
  --version v1
```

```
case            status  failed_assertions
--------------  ------  ------------------
greeting        FAIL    contains
json-user       PASS
classification  PASS
regex-date      PASS
refusal         PASS

4/5 cases passed (80%)
```

Exit code is `0` if every case passes, `1` otherwise.

### Compare two versions

```bash
promptdiff compare \
  --suite examples/suite.yaml \
  --fixtures examples/fixtures \
  --base v1 --head v2
```

```
case            base -> head    verdict  assertion transitions
--------------  --------------  -------  ----------------------------------------
greeting        FAIL -> PASS    CHANGED  improved: contains
json-user       PASS -> FAIL    CHANGED  regressed: is_valid_json, json_has_keys, json_schema
classification  PASS -> FAIL    CHANGED  regressed: one_of
regex-date      PASS -> FAIL    CHANGED  regressed: matches_regex
refusal         PASS -> PASS    same

suite: example-assistant-suite
base=v1  head=v2
pass rate: 80% -> 40% (-40%)
regressions: 3   improvements: 1
```

Exit code is `1` because regressions were found (regardless of the
pass-rate delta's sign -- one regressed case is enough). Pass
`--allow-regression` to acknowledge the regressions and exit `0` anyway
(useful when you are intentionally trading one behaviour for another and
want CI to still record the report).

Add `--format json` to either subcommand for machine-readable output, and
`--text-diff` to `compare` to include a unified diff of the raw outputs
for cases whose text changed.

### Plugging in a real provider

promptdiff ships only `ReplayRunner` because that is what keeps the tool
(and its test suite) fully offline. To evaluate a live prompt, write a
small adapter with the same `run` method and call the library directly
instead of going through `ReplayRunner`:

```python
from promptdiff import Suite, load_suite, run_suite, compare_versions
from your_provider_sdk import Client

class LiveRunner:
    def __init__(self, client: Client, system_prompt: str) -> None:
        self.client = client
        self.system_prompt = system_prompt

    def run(self, case_id: str, input_text: str) -> str:
        response = self.client.complete(
            system=self.system_prompt,
            user=input_text,
        )
        return response.text

suite = load_suite("examples/suite.yaml")
results = run_suite(suite, LiveRunner(client, prompt_v2_text))

# Or compare a live version against a recorded baseline:
from promptdiff import ReplayRunner
report = compare_versions(
    suite,
    ReplayRunner("fixtures", "v1"),
    LiveRunner(client, prompt_v2_text),
    base_version="v1",
    head_version="live",
)
```

Any object with a `run(case_id: str, input_text: str) -> str` method
satisfies the `Runner` protocol -- there is nothing to subclass.

To record a fixture for `ReplayRunner`, run your provider once per case
and save the raw output text to
`<fixtures_dir>/<version>/<case_id>.txt` (or `.json` for JSON-producing
cases -- both are read identically as plain text).

## Suite format

A suite is a YAML (or JSON) document:

```yaml
name: optional-suite-name   # optional, shown in compare output
version: 1                  # optional, defaults to 1

cases:
  - id: unique-case-id       # required, unique within the suite
    description: optional human-readable note
    input: "the prompt input for this case"   # required
    assertions:                                # required, non-empty
      - type: contains
        value: "expected substring"
```

### Assertion types

| type | required fields | optional fields | passes when |
|---|---|---|---|
| `contains` | `value` | `case_sensitive` (default `true`) | output contains `value` |
| `not_contains` | `value` | `case_sensitive` (default `true`) | output does not contain `value` |
| `matches_regex` | `pattern` | `flags` (any of `i`, `m`, `s`) | `re.search(pattern, output)` finds a match |
| `is_valid_json` | - | - | `output` parses as JSON |
| `json_has_keys` | `keys` (list of str) | - | `output` parses as a JSON object containing every key in `keys` |
| `json_schema` | `schema` (a JSON Schema, Draft 2020-12) | - | `output` parses as JSON and validates against `schema` |
| `max_length` | `value` (int) | - | `len(output) <= value` |
| `starts_with` | `value` | `case_sensitive` (default `true`) | output starts with `value` |
| `one_of` | `values` (list of str) | `case_sensitive` (default `true`), `strip` (default `true`) | output (optionally stripped/lowercased) equals one of `values` |

An invalid suite file (missing fields, unknown assertion type, an
invalid regex pattern, an invalid JSON Schema) raises a `SuiteParseError`
or `AssertionSpecError` with a message naming the offending case and
field; the CLI prints it to stderr and exits `2`.

## Examples

`examples/suite.yaml` is a complete, runnable suite covering every
assertion type, with two fixture sets under `examples/fixtures/` (`v1`
and `v2`) that intentionally demonstrate a mix of regressions and one
improvement -- see the Usage section above for the exact output it
produces.

## Testing

```bash
./.venv/Scripts/python.exe -m pytest       # Windows
./.venv/bin/python -m pytest                # macOS/Linux
ruff check .
mypy
```

The test suite covers every assertion type in both directions (fires and
correctly does not fire), suite parsing errors, `ReplayRunner` including
the missing-fixture error path, and the version-comparison logic
(regressions, improvements, unchanged cases, pass-rate math). It runs
entirely offline -- there is no network access anywhere in the test
path.

## Security

- promptdiff makes no network requests of any kind. `ReplayRunner` only
  reads local files.
- Suite files are parsed with `yaml.safe_load`, never `yaml.load`, so a
  malicious suite file cannot execute arbitrary Python objects.
- `json_schema` validation uses the `jsonschema` library's validator
  against Draft 2020-12; schemas are only used for validation, never
  executed.
- No secrets, API keys, or credentials are read, stored, or required by
  any code path in this repository.

## License

MIT. See [LICENSE](LICENSE).
