"""The pluggable runner interface.

promptdiff never calls a model itself. A Runner is anything with a
`run(case_id, input_text) -> str` method; promptdiff calls it once per
case and checks the returned text against that case's assertions.

ReplayRunner is the runner shipped here: it reads pre-recorded outputs
from a fixtures directory, which is what makes the whole tool testable
and usable completely offline, with no API keys and no network access.
To evaluate a *live* prompt, write a small adapter class with the same
`run` method that calls your model provider of choice -- see the
README's "Plugging in a real provider" section for a template.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


class FixtureNotFoundError(FileNotFoundError):
    """Raised by ReplayRunner when no recorded output exists for a case."""


class FixtureError(ValueError):
    """Raised by ReplayRunner for a fixture it refuses or fails to read: a
    case id / version that would resolve outside the fixtures directory, or
    a fixture that is not valid UTF-8."""


@runtime_checkable
class Runner(Protocol):
    """Anything that can produce an output for a given case is a Runner.

    Implementations are free to call a live model, a cache, or -- as with
    ReplayRunner -- replay a fixture from disk. promptdiff only ever calls
    `run`; it does not care how the output was produced.
    """

    def run(self, case_id: str, input_text: str) -> str:
        """Return the output text for the given case's input."""
        ...


_FIXTURE_EXTENSIONS = (".txt", ".json")


class ReplayRunner:
    """A Runner that replays pre-recorded outputs from a fixtures directory.

    Fixtures are stored as ``<fixtures_dir>/<version>/<case_id>.txt`` (or
    ``.json`` -- both are read as plain text; the extension is just a
    convenience for keeping structured fixtures readable). This makes
    promptdiff fully offline: record a model's output once, commit it,
    and every later run and comparison replays that same recorded text
    with zero network access.
    """

    def __init__(self, fixtures_dir: str | Path, version: str) -> None:
        self.fixtures_dir = Path(fixtures_dir)
        self.version = version
        self._version_dir = self.fixtures_dir / version

    def _fixture_path(self, case_id: str) -> Path:
        # Case ids and versions come from the suite file and the command
        # line; neither may steer the read outside the fixtures directory
        # (e.g. an id of "../../secrets"), since outputs are echoed in
        # reports and --text-diff.
        root = self.fixtures_dir.resolve()
        version_dir = (root / self.version).resolve()
        if version_dir == root or not version_dir.is_relative_to(root):
            raise FixtureError(
                f"version {self.version!r} would read outside the fixtures directory"
            )
        target = (version_dir / case_id).resolve()
        if target == version_dir or not target.is_relative_to(version_dir):
            raise FixtureError(
                f"case id {case_id!r} would read outside the fixtures directory"
            )
        for ext in _FIXTURE_EXTENSIONS:
            candidate = self._version_dir / f"{case_id}{ext}"
            if candidate.is_file():
                return candidate
        # No fixture found under any known extension; report the primary
        # expected path in the error for a clear, actionable message.
        return self._version_dir / f"{case_id}.txt"

    def run(self, case_id: str, input_text: str) -> str:
        path = self._fixture_path(case_id)
        if not path.is_file():
            raise FixtureNotFoundError(
                f"no fixture found for case {case_id!r} at version {self.version!r} "
                f"(looked for {self._version_dir / (case_id + '.txt')} and "
                f"{self._version_dir / (case_id + '.json')})"
            )
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise FixtureError(
                f"fixture for case {case_id!r} at version {self.version!r} is not valid "
                f"UTF-8 (byte offset {exc.start})"
            ) from None

    def has_fixture(self, case_id: str) -> bool:
        return self._fixture_path(case_id).is_file()
