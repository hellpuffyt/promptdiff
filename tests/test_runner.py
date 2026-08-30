"""Tests for ReplayRunner and the Runner protocol."""

from __future__ import annotations

from pathlib import Path

import pytest

from promptdiff.runner import FixtureNotFoundError, ReplayRunner, Runner


@pytest.fixture
def fixtures_dir(tmp_path: Path) -> Path:
    v1 = tmp_path / "v1"
    v1.mkdir()
    (v1 / "greeting.txt").write_text("hello there", encoding="utf-8")
    (v1 / "json-case.json").write_text('{"a": 1}', encoding="utf-8")
    return tmp_path


class TestReplayRunner:
    def test_reads_txt_fixture(self, fixtures_dir: Path) -> None:
        runner = ReplayRunner(fixtures_dir, "v1")
        assert runner.run("greeting", "irrelevant input") == "hello there"

    def test_reads_json_fixture_as_text(self, fixtures_dir: Path) -> None:
        runner = ReplayRunner(fixtures_dir, "v1")
        assert runner.run("json-case", "irrelevant") == '{"a": 1}'

    def test_missing_fixture_raises(self, fixtures_dir: Path) -> None:
        runner = ReplayRunner(fixtures_dir, "v1")
        with pytest.raises(FixtureNotFoundError):
            runner.run("nonexistent-case", "x")

    def test_missing_version_directory_raises(self, fixtures_dir: Path) -> None:
        runner = ReplayRunner(fixtures_dir, "nonexistent-version")
        with pytest.raises(FixtureNotFoundError):
            runner.run("greeting", "x")

    def test_has_fixture_true(self, fixtures_dir: Path) -> None:
        runner = ReplayRunner(fixtures_dir, "v1")
        assert runner.has_fixture("greeting") is True

    def test_has_fixture_false(self, fixtures_dir: Path) -> None:
        runner = ReplayRunner(fixtures_dir, "v1")
        assert runner.has_fixture("nonexistent-case") is False

    def test_accepts_str_path(self, fixtures_dir: Path) -> None:
        runner = ReplayRunner(str(fixtures_dir), "v1")
        assert runner.run("greeting", "x") == "hello there"

    def test_error_message_mentions_case_and_version(self, fixtures_dir: Path) -> None:
        runner = ReplayRunner(fixtures_dir, "v1")
        with pytest.raises(FixtureNotFoundError, match="nonexistent-case"):
            runner.run("nonexistent-case", "x")

    def test_satisfies_runner_protocol(self, fixtures_dir: Path) -> None:
        runner = ReplayRunner(fixtures_dir, "v1")
        assert isinstance(runner, Runner)

    def test_plain_object_with_run_method_satisfies_protocol(self) -> None:
        class Custom:
            def run(self, case_id: str, input_text: str) -> str:
                return "static output"

        assert isinstance(Custom(), Runner)
        assert Custom().run("x", "y") == "static output"
