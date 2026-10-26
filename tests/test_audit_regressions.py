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


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):  # e.g. Windows without symlink rights
        pytest.skip("symlinks are not available on this platform")


def test_fixture_file_symlinked_outside_the_fixtures_directory_is_refused(
    layout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Before: fixtures/v1/leak.txt -> <tmp>/outside.txt was followed and
    # "not a fixture" appeared in the report.
    _symlink_or_skip(layout / "fixtures" / "v1" / "leak.txt", layout / "outside.txt")
    runner = ReplayRunner(layout / "fixtures", "v1")
    with pytest.raises(FixtureError, match="outside the fixtures directory"):
        runner.run("leak", "x")
    suite = layout / "suite.yaml"
    suite.write_text(
        "cases:\n  - id: leak\n    input: hi\n"
        "    assertions:\n      - {type: contains, value: x}\n",
        encoding="utf-8",
    )
    rc = main(["run", "--suite", str(suite), "--fixtures", str(layout / "fixtures"),
               "--version", "v1", "--format", "json"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "not a fixture" not in captured.out + captured.err


def test_fixture_file_symlinked_inside_the_fixtures_directory_still_reads(
    layout: Path,
) -> None:
    v1 = layout / "fixtures" / "v1"
    _symlink_or_skip(v1 / "alias.txt", v1 / "ok.txt")
    assert ReplayRunner(layout / "fixtures", "v1").run("alias", "x") == "hello"


def test_text_diff_puts_each_line_on_its_own_line_without_trailing_newline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Before: fixtures with no trailing newline printed "-old+new" on one line.
    for version, text in (("v1", "old"), ("v2", "new")):
        (tmp_path / "fixtures" / version).mkdir(parents=True)
        (tmp_path / "fixtures" / version / "c.txt").write_text(text, encoding="utf-8")
    suite = tmp_path / "suite.yaml"
    suite.write_text(
        "cases:\n  - id: c\n    input: hi\n    assertions:\n      - {type: contains, value: e}\n",
        encoding="utf-8",
    )
    main(["compare", "--suite", str(suite), "--fixtures", str(tmp_path / "fixtures"),
          "--base", "v1", "--head", "v2", "--text-diff"])
    lines = capsys.readouterr().out.splitlines()
    assert "-old" in lines
    assert "+new" in lines
    assert "-old+new" not in "\n".join(lines)
