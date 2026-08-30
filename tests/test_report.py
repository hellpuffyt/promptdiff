"""Tests for human table and JSON rendering."""

from __future__ import annotations

import json

from promptdiff.compare import compare_versions
from promptdiff.evaluate import run_suite
from promptdiff.report import (
    render_compare_json,
    render_compare_table,
    render_run_json,
    render_run_table,
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
"""


class _DictRunner:
    def __init__(self, outputs: dict[str, str]) -> None:
        self.outputs = outputs

    def run(self, case_id: str, input_text: str) -> str:
        return self.outputs[case_id]


class TestRunRendering:
    def test_table_shows_pass(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        results = run_suite(suite, _DictRunner({"c1": "ok"}))
        table = render_run_table(results)
        assert "c1" in table
        assert "PASS" in table
        assert "1/1 cases passed (100%)" in table

    def test_table_shows_fail_and_failed_assertion_type(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        results = run_suite(suite, _DictRunner({"c1": "nope"}))
        table = render_run_table(results)
        assert "FAIL" in table
        assert "contains" in table
        assert "0/1 cases passed (0%)" in table

    def test_json_is_valid_and_has_expected_shape(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        results = run_suite(suite, _DictRunner({"c1": "ok"}))
        payload = json.loads(render_run_json(results))
        assert payload["total"] == 1
        assert payload["passed"] == 1
        assert payload["pass_rate"] == 1.0
        assert payload["cases"][0]["case_id"] == "c1"
        assert payload["cases"][0]["passed"] is True
        assert payload["cases"][0]["assertions"][0]["type"] == "contains"


class TestCompareRendering:
    def test_table_includes_pass_rate_delta_and_counts(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        report = compare_versions(
            suite,
            _DictRunner({"c1": "ok"}),
            _DictRunner({"c1": "nope"}),
            base_version="v1",
            head_version="v2",
        )
        table = render_compare_table(report)
        assert "v1" in table
        assert "v2" in table
        assert "regressions: 1" in table
        assert "improvements: 0" in table
        assert "regressed: contains" in table

    def test_table_with_text_diff_included(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        report = compare_versions(
            suite,
            _DictRunner({"c1": "ok line"}),
            _DictRunner({"c1": "ok line changed"}),
            base_version="v1",
            head_version="v2",
        )
        table = render_compare_table(report, show_text_diff=True)
        assert "text diffs:" in table
        assert "--- c1 ---" in table

    def test_table_without_text_diff_omits_section(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        report = compare_versions(
            suite,
            _DictRunner({"c1": "ok line"}),
            _DictRunner({"c1": "ok line changed"}),
            base_version="v1",
            head_version="v2",
        )
        table = render_compare_table(report, show_text_diff=False)
        assert "text diffs:" not in table

    def test_json_shape(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        report = compare_versions(
            suite,
            _DictRunner({"c1": "ok"}),
            _DictRunner({"c1": "nope"}),
            base_version="v1",
            head_version="v2",
        )
        payload = json.loads(render_compare_json(report))
        assert payload["base_version"] == "v1"
        assert payload["head_version"] == "v2"
        assert payload["regression_count"] == 1
        assert payload["cases"][0]["has_regression"] is True
        assert "text_diff" not in payload["cases"][0]

    def test_json_includes_text_diff_when_requested_and_changed(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        report = compare_versions(
            suite,
            _DictRunner({"c1": "ok line"}),
            _DictRunner({"c1": "ok line changed"}),
            base_version="v1",
            head_version="v2",
        )
        payload = json.loads(render_compare_json(report, show_text_diff=True))
        assert "text_diff" in payload["cases"][0]

    def test_json_omits_text_diff_when_unchanged_even_if_requested(self) -> None:
        suite = parse_suite_text(SUITE_TEXT)
        report = compare_versions(
            suite,
            _DictRunner({"c1": "ok"}),
            _DictRunner({"c1": "ok"}),
            base_version="v1",
            head_version="v2",
        )
        payload = json.loads(render_compare_json(report, show_text_diff=True))
        assert "text_diff" not in payload["cases"][0]
