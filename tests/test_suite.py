"""Tests for suite file parsing and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from promptdiff.suite import SuiteParseError, load_suite, parse_suite_text

VALID_YAML = """
name: my-suite
version: 1
cases:
  - id: case-1
    input: "hello"
    assertions:
      - type: contains
        value: "hello"
  - id: case-2
    description: second case
    input: "world"
    assertions:
      - type: max_length
        value: 100
"""

VALID_JSON = """
{
  "name": "my-suite",
  "cases": [
    {"id": "case-1", "input": "hi", "assertions": [{"type": "contains", "value": "hi"}]}
  ]
}
"""


class TestParseValidSuites:
    def test_parses_two_cases(self) -> None:
        suite = parse_suite_text(VALID_YAML)
        assert suite.case_ids() == ["case-1", "case-2"]
        assert suite.name == "my-suite"
        assert suite.version == 1

    def test_case_description_optional(self) -> None:
        suite = parse_suite_text(VALID_YAML)
        assert suite.get("case-1").description is None
        assert suite.get("case-2").description == "second case"

    def test_get_unknown_case_raises_keyerror(self) -> None:
        suite = parse_suite_text(VALID_YAML)
        with pytest.raises(KeyError):
            suite.get("nonexistent")

    def test_parses_json_when_forced(self) -> None:
        suite = parse_suite_text(VALID_JSON, fmt="json")
        assert suite.case_ids() == ["case-1"]

    def test_json_is_valid_yaml_too(self) -> None:
        # JSON is a subset of YAML, so the default (yaml) parser should
        # also accept a JSON document without fmt="json".
        suite = parse_suite_text(VALID_JSON)
        assert suite.case_ids() == ["case-1"]

    def test_name_defaults_to_none(self) -> None:
        suite = parse_suite_text(
            """
cases:
  - id: c1
    input: "x"
    assertions: [{type: contains, value: x}]
"""
        )
        assert suite.name is None

    def test_version_defaults_to_one(self) -> None:
        suite = parse_suite_text(
            """
cases:
  - id: c1
    input: "x"
    assertions: [{type: contains, value: x}]
"""
        )
        assert suite.version == 1


class TestSuiteErrors:
    def test_top_level_not_a_mapping(self) -> None:
        with pytest.raises(SuiteParseError, match="mapping"):
            parse_suite_text("- just\n- a\n- list\n")

    def test_missing_cases(self) -> None:
        with pytest.raises(SuiteParseError, match="cases"):
            parse_suite_text("name: x\n")

    def test_cases_not_a_list(self) -> None:
        with pytest.raises(SuiteParseError, match="cases"):
            parse_suite_text("cases: not-a-list\n")

    def test_empty_cases_list(self) -> None:
        with pytest.raises(SuiteParseError, match="cases"):
            parse_suite_text("cases: []\n")

    def test_case_not_a_mapping(self) -> None:
        with pytest.raises(SuiteParseError, match="cases\\[0\\]"):
            parse_suite_text("cases:\n  - just a string\n")

    def test_case_missing_id(self) -> None:
        with pytest.raises(SuiteParseError, match="id"):
            parse_suite_text(
                'cases:\n  - input: "x"\n    assertions: [{type: contains, value: x}]\n'
            )

    def test_case_missing_input(self) -> None:
        with pytest.raises(SuiteParseError, match="input"):
            parse_suite_text(
                "cases:\n  - id: c1\n    assertions: [{type: contains, value: x}]\n"
            )

    def test_case_missing_assertions(self) -> None:
        with pytest.raises(SuiteParseError, match="assertions"):
            parse_suite_text('cases:\n  - id: c1\n    input: "x"\n')

    def test_case_empty_assertions(self) -> None:
        with pytest.raises(SuiteParseError, match="assertions"):
            parse_suite_text('cases:\n  - id: c1\n    input: "x"\n    assertions: []\n')

    def test_duplicate_case_ids(self) -> None:
        text = """
cases:
  - id: dup
    input: "a"
    assertions: [{type: contains, value: a}]
  - id: dup
    input: "b"
    assertions: [{type: contains, value: b}]
"""
        with pytest.raises(SuiteParseError, match="duplicate"):
            parse_suite_text(text)

    def test_invalid_assertion_in_case_reports_case_id(self) -> None:
        text = 'cases:\n  - id: c1\n    input: "x"\n    assertions: [{type: nonexistent}]\n'
        with pytest.raises(SuiteParseError, match="c1"):
            parse_suite_text(text)

    def test_invalid_yaml_syntax(self) -> None:
        with pytest.raises(SuiteParseError, match="YAML"):
            parse_suite_text("cases: [unclosed\n")

    def test_invalid_json_syntax(self) -> None:
        with pytest.raises(SuiteParseError, match="JSON"):
            parse_suite_text("{not valid json", fmt="json")

    def test_description_wrong_type(self) -> None:
        text = (
            'cases:\n  - id: c1\n    input: "x"\n    description: 5\n'
            "    assertions: [{type: contains, value: x}]\n"
        )
        with pytest.raises(SuiteParseError, match="description"):
            parse_suite_text(text)

    def test_version_wrong_type(self) -> None:
        text = (
            'version: "not-an-int"\ncases:\n  - id: c1\n    input: "x"\n'
            "    assertions: [{type: contains, value: x}]\n"
        )
        with pytest.raises(SuiteParseError, match="version"):
            parse_suite_text(text)

    def test_name_wrong_type(self) -> None:
        text = (
            'name: [1, 2]\ncases:\n  - id: c1\n    input: "x"\n'
            "    assertions: [{type: contains, value: x}]\n"
        )
        with pytest.raises(SuiteParseError, match="name"):
            parse_suite_text(text)

    def test_input_wrong_type(self) -> None:
        text = "cases:\n  - id: c1\n    input: 5\n    assertions: [{type: contains, value: x}]\n"
        with pytest.raises(SuiteParseError, match="input"):
            parse_suite_text(text)


class TestLoadSuiteFromDisk:
    def test_loads_yaml_file(self, tmp_path: Path) -> None:
        suite_file = tmp_path / "suite.yaml"
        suite_file.write_text(VALID_YAML, encoding="utf-8")
        suite = load_suite(suite_file)
        assert suite.case_ids() == ["case-1", "case-2"]

    def test_loads_json_file_by_extension(self, tmp_path: Path) -> None:
        suite_file = tmp_path / "suite.json"
        suite_file.write_text(VALID_JSON, encoding="utf-8")
        suite = load_suite(suite_file)
        assert suite.case_ids() == ["case-1"]

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(SuiteParseError, match="not found"):
            load_suite(tmp_path / "nonexistent.yaml")

    def test_accepts_str_path(self, tmp_path: Path) -> None:
        suite_file = tmp_path / "suite.yaml"
        suite_file.write_text(VALID_YAML, encoding="utf-8")
        suite = load_suite(str(suite_file))
        assert suite.case_ids() == ["case-1", "case-2"]
