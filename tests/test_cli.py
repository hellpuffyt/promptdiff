"""Tests for the CLI: exit codes, formats, error handling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptdiff.cli import EXIT_FAILURES_OR_REGRESSIONS, EXIT_OK, EXIT_USAGE_ERROR, main

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_SUITE = REPO_ROOT / "examples" / "suite.yaml"
EXAMPLE_FIXTURES = REPO_ROOT / "examples" / "fixtures"


@pytest.fixture
def suite_file(tmp_path: Path) -> Path:
    suite = tmp_path / "suite.yaml"
    suite.write_text(
        """
cases:
  - id: c1
    input: "x"
    assertions:
      - type: contains
        value: "ok"
""",
        encoding="utf-8",
    )
    return suite


@pytest.fixture
def fixtures_dir(tmp_path: Path) -> Path:
    v1 = tmp_path / "v1"
    v1.mkdir()
    (v1 / "c1.txt").write_text("ok", encoding="utf-8")
    v2 = tmp_path / "v2"
    v2.mkdir()
    (v2 / "c1.txt").write_text("totally different response", encoding="utf-8")
    return tmp_path


def _run_args(suite: Path, fixtures: Path, version: str, *extra: str) -> list[str]:
    return [
        "run",
        "--suite", str(suite),
        "--fixtures", str(fixtures),
        "--version", version,
        *extra,
    ]


def _compare_args(suite: Path, fixtures: Path, base: str, head: str, *extra: str) -> list[str]:
    return [
        "compare",
        "--suite", str(suite),
        "--fixtures", str(fixtures),
        "--base", base,
        "--head", head,
        *extra,
    ]


class TestRunCommand:
    def test_exit_zero_on_all_pass(self, suite_file: Path, fixtures_dir: Path) -> None:
        code = main(_run_args(suite_file, fixtures_dir, "v1"))
        assert code == EXIT_OK

    def test_exit_one_on_failure(self, suite_file: Path, fixtures_dir: Path) -> None:
        code = main(_run_args(suite_file, fixtures_dir, "v2"))
        assert code == EXIT_FAILURES_OR_REGRESSIONS

    def test_json_format(
        self, suite_file: Path, fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(_run_args(suite_file, fixtures_dir, "v1", "--format", "json"))
        payload = json.loads(capsys.readouterr().out)
        assert payload["total"] == 1

    def test_table_format_default(
        self, suite_file: Path, fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(_run_args(suite_file, fixtures_dir, "v1"))
        out = capsys.readouterr().out
        assert "case" in out
        assert "status" in out

    def test_bad_suite_path_exits_usage_error(
        self, fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(_run_args(Path("does-not-exist.yaml"), fixtures_dir, "v1"))
        assert code == EXIT_USAGE_ERROR
        assert "error:" in capsys.readouterr().err

    def test_missing_fixture_exits_usage_error(
        self, suite_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        empty_fixtures = tmp_path / "empty"
        empty_fixtures.mkdir()
        code = main(_run_args(suite_file, empty_fixtures, "v1"))
        assert code == EXIT_USAGE_ERROR
        assert "error:" in capsys.readouterr().err

    def test_malformed_suite_exits_usage_error(
        self, tmp_path: Path, fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad_suite = tmp_path / "bad.yaml"
        bad_suite.write_text("cases: []\n", encoding="utf-8")
        code = main(_run_args(bad_suite, fixtures_dir, "v1"))
        assert code == EXIT_USAGE_ERROR
        assert "error:" in capsys.readouterr().err


class TestCompareCommand:
    def test_exit_one_on_regression(self, suite_file: Path, fixtures_dir: Path) -> None:
        code = main(_compare_args(suite_file, fixtures_dir, "v1", "v2"))
        assert code == EXIT_FAILURES_OR_REGRESSIONS

    def test_allow_regression_overrides_exit_code(
        self, suite_file: Path, fixtures_dir: Path
    ) -> None:
        code = main(_compare_args(suite_file, fixtures_dir, "v1", "v2", "--allow-regression"))
        assert code == EXIT_OK

    def test_exit_zero_when_no_regression(self, suite_file: Path, fixtures_dir: Path) -> None:
        code = main(_compare_args(suite_file, fixtures_dir, "v1", "v1"))
        assert code == EXIT_OK

    def test_json_format(
        self, suite_file: Path, fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(_compare_args(suite_file, fixtures_dir, "v1", "v2", "--format", "json"))
        payload = json.loads(capsys.readouterr().out)
        assert payload["regression_count"] == 1

    def test_text_diff_flag(
        self, suite_file: Path, fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(_compare_args(suite_file, fixtures_dir, "v1", "v2", "--text-diff"))
        assert "text diffs:" in capsys.readouterr().out


class TestExampleSuiteSmoke:
    def test_run_v1_exits_one_due_to_seeded_greeting_bug(self) -> None:
        code = main(_run_args(EXAMPLE_SUITE, EXAMPLE_FIXTURES, "v1"))
        assert code == EXIT_FAILURES_OR_REGRESSIONS

    def test_compare_v1_v2_reports_regressions_and_improvements(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(
            _compare_args(
                EXAMPLE_SUITE,
                EXAMPLE_FIXTURES,
                "v1",
                "v2",
                "--format", "json",
                "--allow-regression",
            )
        )
        assert code == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["regression_count"] == 3
        assert payload["improvement_count"] == 1


class TestArgParsing:
    def test_no_command_exits_nonzero(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0

    def test_invalid_format_choice_exits_nonzero(
        self, suite_file: Path, fixtures_dir: Path
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(_run_args(suite_file, fixtures_dir, "v1", "--format", "xml"))
        assert exc_info.value.code != 0
