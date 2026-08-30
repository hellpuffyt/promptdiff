"""Loading and validating suite files.

A suite is a YAML or JSON document describing a fixed set of test cases,
each with an input and a list of model-free assertions to run against the
output produced for that input. See the README's "Suite format" section
for the full schema and examples/suite.yaml for a worked example.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from promptdiff.assertions import Assertion, AssertionSpecError, parse_assertion


class SuiteParseError(ValueError):
    """Raised when a suite file is malformed."""


@dataclass(frozen=True)
class Case:
    """A single test case: an input and the assertions its output must satisfy."""

    id: str
    input: str
    assertions: tuple[Assertion, ...]
    description: str | None = None


@dataclass(frozen=True)
class Suite:
    """A parsed, validated suite: a fixed list of cases."""

    cases: tuple[Case, ...]
    version: int = 1
    name: str | None = None

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for case in self.cases:
            if case.id in seen:
                raise SuiteParseError(f"duplicate case id: {case.id!r}")
            seen.add(case.id)

    def case_ids(self) -> list[str]:
        return [c.id for c in self.cases]

    def get(self, case_id: str) -> Case:
        for case in self.cases:
            if case.id == case_id:
                return case
        raise KeyError(case_id)


def _parse_document(raw: Any, *, source: str) -> Suite:
    if not isinstance(raw, dict):
        raise SuiteParseError(f"{source}: top-level document must be a mapping/object")

    cases_raw = raw.get("cases")
    if cases_raw is None:
        raise SuiteParseError(f"{source}: missing required field 'cases'")
    if not isinstance(cases_raw, list) or not cases_raw:
        raise SuiteParseError(f"{source}: 'cases' must be a non-empty list")

    cases: list[Case] = []
    for index, case_raw in enumerate(cases_raw):
        if not isinstance(case_raw, dict):
            raise SuiteParseError(f"{source}: cases[{index}] must be a mapping/object")

        case_id = case_raw.get("id")
        if not case_id or not isinstance(case_id, str):
            raise SuiteParseError(f"{source}: cases[{index}] is missing required field 'id'")

        input_text = case_raw.get("input")
        if input_text is None or not isinstance(input_text, str):
            raise SuiteParseError(
                f"{source}: case {case_id!r} is missing required string field 'input'"
            )

        assertions_raw = case_raw.get("assertions")
        if assertions_raw is None:
            raise SuiteParseError(
                f"{source}: case {case_id!r} is missing required field 'assertions'"
            )
        if not isinstance(assertions_raw, list) or not assertions_raw:
            raise SuiteParseError(
                f"{source}: case {case_id!r} must have a non-empty 'assertions' list"
            )

        try:
            assertions = tuple(parse_assertion(a) for a in assertions_raw)
        except AssertionSpecError as exc:
            raise SuiteParseError(f"{source}: case {case_id!r}: {exc}") from exc

        description = case_raw.get("description")
        if description is not None and not isinstance(description, str):
            raise SuiteParseError(f"{source}: case {case_id!r}: 'description' must be a string")

        cases.append(
            Case(id=case_id, input=input_text, assertions=assertions, description=description)
        )

    version = raw.get("version", 1)
    if not isinstance(version, int):
        raise SuiteParseError(f"{source}: 'version' must be an integer")

    name = raw.get("name")
    if name is not None and not isinstance(name, str):
        raise SuiteParseError(f"{source}: 'name' must be a string")

    try:
        return Suite(cases=tuple(cases), version=version, name=name)
    except SuiteParseError as exc:
        raise SuiteParseError(f"{source}: {exc}") from exc


def parse_suite_text(text: str, *, source: str = "<string>", fmt: str | None = None) -> Suite:
    """Parse suite text as YAML (default) or JSON.

    JSON is a subset of YAML, so fmt is normally unnecessary; pass
    fmt='json' or fmt='yaml' to force a parser explicitly.
    """
    if fmt == "json":
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SuiteParseError(f"{source}: invalid JSON: {exc}") from exc
    else:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise SuiteParseError(f"{source}: invalid YAML: {exc}") from exc
    return _parse_document(raw, source=source)


def load_suite(path: str | Path) -> Suite:
    """Load and validate a suite file from disk (YAML or JSON, by extension)."""
    p = Path(path)
    if not p.is_file():
        raise SuiteParseError(f"suite file not found: {p}")
    text = p.read_text(encoding="utf-8")
    fmt = "json" if p.suffix.lower() == ".json" else "yaml"
    return parse_suite_text(text, source=str(p), fmt=fmt)
