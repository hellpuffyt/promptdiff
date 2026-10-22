"""Regression tests for defects found in the production-readiness audit.
All runners here are ReplayRunner over temporary fixtures (no model calls)."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from promptdiff.assertions import AssertionSpecError, MatchesRegexAssertion
from promptdiff.cli import main
from promptdiff.runner import FixtureError, ReplayRunner


@pytest.fixture
def layout(tmp_path: Path) -> Path:
    (tmp_path / "fixtures" / "v1").mkdir(parents=True)
    (tmp_path / "fixtures" / "v1" / "ok.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("not a fixture", encoding="utf-8")
    (tmp_path / "fixtures" / "secret.txt").write_text("not a fixture", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "case_id", ["../../outside", "../secret", "/etc/hosts", "sub/../../secret"]
)
def test_case_id_cannot_escape_the_fixtures_directory(layout: Path, case_id: str) -> None:
    # Before: "../../outside" read <tmp>/outside.txt and fed it to the report.
    runner = ReplayRunner(layout / "fixtures", "v1")
    with pytest.raises(FixtureError):
        runner.run(case_id, "x")


@pytest.mark.parametrize("version", ["..", "../..", "/tmp", "."])
def test_version_cannot_escape_the_fixtures_directory(layout: Path, version: str) -> None:
    with pytest.raises(FixtureError):
        ReplayRunner(layout / "fixtures", version).run("ok", "x")


def test_normal_case_still_reads(layout: Path) -> None:
    assert ReplayRunner(layout / "fixtures", "v1").run("ok", "x") == "hello"


def test_cli_reports_escape_attempt_as_usage_error(
    layout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    suite = layout / "suite.yaml"
    suite.write_text(
        'cases:\n  - id: "../../outside"\n    input: hi\n'
        "    assertions:\n      - {type: contains, value: x}\n",
        encoding="utf-8",
    )
    rc = main(["run", "--suite", str(suite), "--fixtures", str(layout / "fixtures"),
               "--version", "v1", "--format", "json"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "not a fixture" not in captured.out + captured.err


def test_invalid_regex_is_rejected_when_the_suite_loads() -> None:
    # Before: only detected once a fixture existed and the case was checked.
    with pytest.raises(AssertionSpecError):
        MatchesRegexAssertion(pattern="(")
    with pytest.raises(AssertionSpecError):
        MatchesRegexAssertion(pattern="a", flags="z")


def test_non_utf8_fixture_is_a_clean_error(
    layout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (layout / "fixtures" / "v1" / "bad.txt").write_bytes(b"x\xff")
    suite = layout / "suite.yaml"
    suite.write_text(
        "cases:\n  - id: bad\n    input: hi\n    assertions:\n      - {type: contains, value: x}\n",
        encoding="utf-8",
    )
    rc = main(["run", "--suite", str(suite), "--fixtures", str(layout / "fixtures"),
               "--version", "v1"])
    assert rc == 2
    assert "not valid UTF-8" in capsys.readouterr().err


def test_network_guard_is_active() -> None:
    with pytest.raises(AssertionError, match="no real LLM calls"):
        socket.create_connection(("example.com", 443))
