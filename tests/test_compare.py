"""Tests for version-comparison logic: transitions, pass-rate deltas, errors."""

from __future__ import annotations

import pytest

from promptdiff.compare import (
    IMPROVEMENT,
    REGRESSION,
    UNCHANGED_FAIL,
    UNCHANGED_PASS,
    compare_versions,
)
from promptdiff.suite import parse_suite_text

SUITE_TEXT = """
name: demo
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

    def run(self, case_id: str, input_text: str) -> str:
        return self.outputs[case_id]


class TestCompareVersions:
    def test_unchanged_pass(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        base = _DictRunner({"c1": "ok", "c2": "ok"})
        head = _DictRunner({"c1": "ok!", "c2": "ok"})
        report = compare_versions(suite, base, head, base_version="v1", head_version="v2")
        c1 = report.cases[0]
        assert c1.base_passed is True
        assert c1.head_passed is True
        assert c1.verdict_changed is False
        assert all(t.kind == UNCHANGED_PASS for t in c1.transitions)

    def test_regression_detected(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        base = _DictRunner({"c1": "ok", "c2": "ok"})
        head = _DictRunner({"c1": "nope", "c2": "ok"})
        report = compare_versions(suite, base, head, base_version="v1", head_version="v2")
        c1 = next(c for c in report.cases if c.case_id == "c1")
        assert c1.has_regression is True
        assert c1.verdict_changed is True
        assert report.has_regressions is True
        assert c1 in report.regressions

    def test_improvement_detected(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        base = _DictRunner({"c1": "nope", "c2": "ok"})
        head = _DictRunner({"c1": "ok", "c2": "ok"})
        report = compare_versions(suite, base, head, base_version="v1", head_version="v2")
        c1 = next(c for c in report.cases if c.case_id == "c1")
        assert c1.has_improvement is True
        assert c1 in report.improvements
        assert report.has_regressions is False
        assert any(t.kind == IMPROVEMENT for t in c1.transitions)

    def test_unchanged_fail(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        base = _DictRunner({"c1": "nope", "c2": "ok"})
        head = _DictRunner({"c1": "still nope", "c2": "ok"})
        report = compare_versions(suite, base, head, base_version="v1", head_version="v2")
        c1 = next(c for c in report.cases if c.case_id == "c1")
        assert c1.verdict_changed is False
        assert any(t.kind == UNCHANGED_FAIL for t in c1.transitions)
        assert c1 not in report.regressions
        assert c1 not in report.improvements

    def test_partial_regression_within_case(self) -> None:
        # c2 has two assertions; only max_length regresses.
        suite = parse_suite_text(SUITE_TEXT)
        base = _DictRunner({"c1": "ok", "c2": "ok"})
        head = _DictRunner({"c1": "ok", "c2": "ok but far too long now"})
        report = compare_versions(suite, base, head, base_version="v1", head_version="v2")
        c2 = next(c for c in report.cases if c.case_id == "c2")
        kinds = {t.assertion_type: t.kind for t in c2.transitions}
        assert kinds["contains"] == UNCHANGED_PASS
        assert kinds["max_length"] == REGRESSION
        assert c2.has_regression is True

    def test_text_changed_true_when_output_differs(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        base = _DictRunner({"c1": "ok", "c2": "ok"})
        head = _DictRunner({"c1": "ok!!!", "c2": "ok"})
        report = compare_versions(suite, base, head, base_version="v1", head_version="v2")
        c1 = next(c for c in report.cases if c.case_id == "c1")
        assert c1.text_changed is True

    def test_text_changed_false_when_output_identical(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        base = _DictRunner({"c1": "ok", "c2": "ok"})
        head = _DictRunner({"c1": "ok", "c2": "ok"})
        report = compare_versions(suite, base, head, base_version="v1", head_version="v2")
        c1 = next(c for c in report.cases if c.case_id == "c1")
        assert c1.text_changed is False

    def test_text_diff_contains_expected_markers(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        base = _DictRunner({"c1": "line one", "c2": "ok"})
        head = _DictRunner({"c1": "line two", "c2": "ok"})
        report = compare_versions(suite, base, head, base_version="v1", head_version="v2")
        c1 = next(c for c in report.cases if c.case_id == "c1")
        diff = c1.text_diff()
        assert "-line one" in diff
        assert "+line two" in diff

    def test_pass_rate_math(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        base = _DictRunner({"c1": "ok", "c2": "ok"})  # both pass -> 1.0
        head = _DictRunner({"c1": "nope", "c2": "ok"})  # one fails -> 0.5
        report = compare_versions(suite, base, head, base_version="v1", head_version="v2")
        assert report.base_pass_rate == 1.0
        assert report.head_pass_rate == 0.5
        assert report.pass_rate_delta == pytest.approx(-0.5)

    def test_suite_name_and_versions_propagate(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        base = _DictRunner({"c1": "ok", "c2": "ok"})
        head = _DictRunner({"c1": "ok", "c2": "ok"})
        report = compare_versions(suite, base, head, base_version="v1", head_version="v2")
        assert report.suite_name == "demo"
        assert report.base_version == "v1"
        assert report.head_version == "v2"

    def test_no_cases_edge_case_pass_rates_are_one(self) -> None:
        from promptdiff.compare import CompareReport

        report = CompareReport(suite_name=None, base_version="a", head_version="b", cases=())
        assert report.base_pass_rate == 1.0
        assert report.head_pass_rate == 1.0
        assert report.pass_rate_delta == 0.0
        assert report.has_regressions is False


class TestPairResultsErrors:
    def test_missing_case_in_head_run_raises(self) -> None:
        from promptdiff.compare import _pair_results
        from promptdiff.evaluate import CaseResult

        base = (CaseResult(case_id="only-in-base", output="x", assertion_results=()),)
        with pytest.raises(ValueError, match="only-in-base"):
            _pair_results(base, ())

    def test_mismatched_assertion_count_raises(self) -> None:
        from promptdiff.assertions import parse_assertion
        from promptdiff.compare import _pair_results
        from promptdiff.evaluate import CaseResult

        one_assertion = parse_assertion({"type": "contains", "value": "x"}).check("x")
        base = (CaseResult(case_id="c1", output="x", assertion_results=(one_assertion,)),)
        head = (CaseResult(case_id="c1", output="x", assertion_results=()),)
        with pytest.raises(ValueError, match="different number"):
            _pair_results(base, head)
