"""Tests for running a suite through a single runner."""

from __future__ import annotations

from promptdiff.evaluate import pass_rate, run_suite
from promptdiff.suite import parse_suite_text

SUITE_TEXT = """
cases:
  - id: c1
    input: "x"
    assertions:
      - type: contains
        value: "ok"
  - id: c2
    input: "y"
    assertions:
      - type: contains
        value: "ok"
      - type: max_length
        value: 5
"""


class _DictRunner:
    def __init__(self, outputs: dict[str, str]) -> None:
        self.outputs = outputs
        self.calls: list[tuple[str, str]] = []

    def run(self, case_id: str, input_text: str) -> str:
        self.calls.append((case_id, input_text))
        return self.outputs[case_id]


class TestRunSuite:
    def test_all_pass(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        runner = _DictRunner({"c1": "ok!", "c2": "ok"})
        results = run_suite(suite, runner)
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_some_fail(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        runner = _DictRunner({"c1": "nope", "c2": "ok"})
        results = run_suite(suite, runner)
        by_id = {r.case_id: r for r in results}
        assert by_id["c1"].passed is False
        assert by_id["c2"].passed is True

    def test_failed_assertions_property(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        runner = _DictRunner({"c1": "ok", "c2": "ok but way too long for the limit"})
        results = run_suite(suite, runner)
        c2 = next(r for r in results if r.case_id == "c2")
        assert c2.passed is False
        failed_types = [a.assertion_type for a in c2.failed_assertions]
        assert failed_types == ["max_length"]

    def test_runner_is_called_with_correct_input(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        runner = _DictRunner({"c1": "ok", "c2": "ok"})
        run_suite(suite, runner)
        assert ("c1", "x") in runner.calls
        assert ("c2", "y") in runner.calls

    def test_preserves_case_order(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        runner = _DictRunner({"c1": "ok", "c2": "ok"})
        results = run_suite(suite, runner)
        assert [r.case_id for r in results] == ["c1", "c2"]


class TestPassRate:
    def test_all_pass_is_one(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        results = run_suite(suite, _DictRunner({"c1": "ok", "c2": "ok"}))
        assert pass_rate(results) == 1.0

    def test_all_fail_is_zero(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        results = run_suite(suite, _DictRunner({"c1": "no", "c2": "no"}))
        assert pass_rate(results) == 0.0

    def test_half_pass(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        results = run_suite(suite, _DictRunner({"c1": "ok", "c2": "no"}))
        assert pass_rate(results) == 0.5

    def test_empty_is_vacuously_one(self) -> None:
        assert pass_rate(()) == 1.0
