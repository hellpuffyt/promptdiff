"""Model-free assertions used to check a single prompt output.

Every assertion here is a pure function of the output text (and, for the
JSON assertions, its parsed structure). None of them call a model or make
any judgement about meaning -- they check syntactic and structural
properties that are cheap, deterministic, and reliable at catching the
regressions that actually happen when a prompt changes: broken JSON,
missing fields, a dropped disclaimer, an output that ballooned in length.

If you need a semantic judgement ("is this still a polite refusal?"),
that is out of scope for promptdiff by design -- see the README's
"What this tool does not do" section.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol, runtime_checkable

import jsonschema
from jsonschema.exceptions import SchemaError as JsonSchemaSchemaError


class AssertionSpecError(ValueError):
    """Raised when an assertion's specification (in the suite file) is invalid."""


@dataclass(frozen=True)
class AssertionResult:
    """The outcome of checking one assertion against one output."""

    assertion_type: str
    passed: bool
    message: str
    description: str


@runtime_checkable
class Assertion(Protocol):
    """An assertion checks an output string and reports pass/fail."""

    type: ClassVar[str]

    def describe(self) -> str:
        """A short, human-readable rendering of this assertion, e.g. contains('ok')."""
        ...

    def check(self, output: str) -> AssertionResult:
        """Check this assertion against a single model output."""
        ...


def _truncate(text: str, limit: int = 80) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


@dataclass(frozen=True)
class ContainsAssertion:
    value: str
    case_sensitive: bool = True
    type: ClassVar[str] = "contains"

    def describe(self) -> str:
        return f"contains({self.value!r}, case_sensitive={self.case_sensitive})"

    def check(self, output: str) -> AssertionResult:
        haystack = output if self.case_sensitive else output.lower()
        needle = self.value if self.case_sensitive else self.value.lower()
        passed = needle in haystack
        message = (
            f"output contains {self.value!r}"
            if passed
            else f"expected output to contain {self.value!r}, got {_truncate(output)!r}"
        )
        return AssertionResult(self.type, passed, message, self.describe())


@dataclass(frozen=True)
class NotContainsAssertion:
    value: str
    case_sensitive: bool = True
    type: ClassVar[str] = "not_contains"

    def describe(self) -> str:
        return f"not_contains({self.value!r}, case_sensitive={self.case_sensitive})"

    def check(self, output: str) -> AssertionResult:
        haystack = output if self.case_sensitive else output.lower()
        needle = self.value if self.case_sensitive else self.value.lower()
        passed = needle not in haystack
        message = (
            f"output does not contain {self.value!r}"
            if passed
            else f"expected output to not contain {self.value!r}, got {_truncate(output)!r}"
        )
        return AssertionResult(self.type, passed, message, self.describe())


@dataclass(frozen=True)
class MatchesRegexAssertion:
    pattern: str
    flags: str = ""
    type: ClassVar[str] = "matches_regex"

    def _re_flags(self) -> int:
        mapping = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}
        result = 0
        for char in self.flags:
            if char not in mapping:
                raise AssertionSpecError(
                    f"matches_regex: unknown flag {char!r}, expected one of {sorted(mapping)}"
                )
            result |= mapping[char]
        return result

    def describe(self) -> str:
        return f"matches_regex({self.pattern!r})"

    def check(self, output: str) -> AssertionResult:
        try:
            compiled = re.compile(self.pattern, self._re_flags())
        except re.error as exc:
            raise AssertionSpecError(
                f"matches_regex: invalid pattern {self.pattern!r}: {exc}"
            ) from exc
        passed = compiled.search(output) is not None
        message = (
            f"output matches /{self.pattern}/"
            if passed
            else f"expected output to match /{self.pattern}/, got {_truncate(output)!r}"
        )
        return AssertionResult(self.type, passed, message, self.describe())


def _try_parse_json(output: str) -> tuple[bool, Any]:
    try:
        return True, json.loads(output)
    except json.JSONDecodeError:
        return False, None


@dataclass(frozen=True)
class IsValidJsonAssertion:
    type: ClassVar[str] = "is_valid_json"

    def describe(self) -> str:
        return "is_valid_json()"

    def check(self, output: str) -> AssertionResult:
        ok, _ = _try_parse_json(output)
        message = "output is valid JSON" if ok else "output is not valid JSON"
        return AssertionResult(self.type, ok, message, self.describe())


@dataclass(frozen=True)
class JsonHasKeysAssertion:
    keys: tuple[str, ...]
    type: ClassVar[str] = "json_has_keys"

    def describe(self) -> str:
        return f"json_has_keys({list(self.keys)!r})"

    def check(self, output: str) -> AssertionResult:
        ok, parsed = _try_parse_json(output)
        if not ok:
            return AssertionResult(
                self.type, False, "output is not valid JSON", self.describe()
            )
        if not isinstance(parsed, dict):
            return AssertionResult(
                self.type,
                False,
                f"output is valid JSON but not an object (got {type(parsed).__name__})",
                self.describe(),
            )
        missing = [k for k in self.keys if k not in parsed]
        passed = not missing
        message = (
            "output JSON has all required keys"
            if passed
            else f"output JSON is missing keys: {missing}"
        )
        return AssertionResult(self.type, passed, message, self.describe())


@dataclass(frozen=True)
class JsonSchemaAssertion:
    schema: dict[str, Any]
    type: ClassVar[str] = "json_schema"

    def __post_init__(self) -> None:
        try:
            jsonschema.Draft202012Validator.check_schema(self.schema)
        except JsonSchemaSchemaError as exc:
            raise AssertionSpecError(f"json_schema: invalid schema: {exc.message}") from exc

    def describe(self) -> str:
        return "json_schema(...)"

    def check(self, output: str) -> AssertionResult:
        ok, parsed = _try_parse_json(output)
        if not ok:
            return AssertionResult(
                self.type, False, "output is not valid JSON", self.describe()
            )
        validator = jsonschema.Draft202012Validator(self.schema)
        errors = sorted(validator.iter_errors(parsed), key=lambda e: e.path)
        passed = not errors
        message = (
            "output JSON matches schema"
            if passed
            else "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])
        )
        return AssertionResult(self.type, passed, message, self.describe())


@dataclass(frozen=True)
class MaxLengthAssertion:
    value: int
    type: ClassVar[str] = "max_length"

    def __post_init__(self) -> None:
        if self.value < 0:
            raise AssertionSpecError("max_length: value must be >= 0")

    def describe(self) -> str:
        return f"max_length({self.value})"

    def check(self, output: str) -> AssertionResult:
        passed = len(output) <= self.value
        message = (
            f"output length {len(output)} <= {self.value}"
            if passed
            else f"output length {len(output)} exceeds max {self.value}"
        )
        return AssertionResult(self.type, passed, message, self.describe())


@dataclass(frozen=True)
class StartsWithAssertion:
    value: str
    case_sensitive: bool = True
    type: ClassVar[str] = "starts_with"

    def describe(self) -> str:
        return f"starts_with({self.value!r}, case_sensitive={self.case_sensitive})"

    def check(self, output: str) -> AssertionResult:
        haystack = output if self.case_sensitive else output.lower()
        needle = self.value if self.case_sensitive else self.value.lower()
        passed = haystack.startswith(needle)
        message = (
            f"output starts with {self.value!r}"
            if passed
            else f"expected output to start with {self.value!r}, got {_truncate(output)!r}"
        )
        return AssertionResult(self.type, passed, message, self.describe())


@dataclass(frozen=True)
class OneOfAssertion:
    values: tuple[str, ...]
    case_sensitive: bool = True
    strip: bool = True
    type: ClassVar[str] = "one_of"

    def describe(self) -> str:
        return f"one_of({list(self.values)!r})"

    def check(self, output: str) -> AssertionResult:
        candidate = output.strip() if self.strip else output
        choices = self.values
        if not self.case_sensitive:
            candidate = candidate.lower()
            choices = tuple(v.lower() for v in choices)
        passed = candidate in choices
        message = (
            "output matches one of the allowed values"
            if passed
            else f"expected one of {list(self.values)!r}, got {_truncate(output)!r}"
        )
        return AssertionResult(self.type, passed, message, self.describe())


_REGISTRY: dict[str, type[Any]] = {
    "contains": ContainsAssertion,
    "not_contains": NotContainsAssertion,
    "matches_regex": MatchesRegexAssertion,
    "is_valid_json": IsValidJsonAssertion,
    "json_has_keys": JsonHasKeysAssertion,
    "json_schema": JsonSchemaAssertion,
    "max_length": MaxLengthAssertion,
    "starts_with": StartsWithAssertion,
    "one_of": OneOfAssertion,
}

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "contains": ("value",),
    "not_contains": ("value",),
    "matches_regex": ("pattern",),
    "is_valid_json": (),
    "json_has_keys": ("keys",),
    "json_schema": ("schema",),
    "max_length": ("value",),
    "starts_with": ("value",),
    "one_of": ("values",),
}


def known_assertion_types() -> list[str]:
    return sorted(_REGISTRY)


def parse_assertion(data: dict[str, Any]) -> Assertion:
    """Build an Assertion from a suite-file assertion mapping.

    Raises AssertionSpecError if the mapping is malformed or refers to an
    unknown assertion type.
    """
    if not isinstance(data, dict):
        raise AssertionSpecError(f"assertion must be a mapping, got {type(data).__name__}")
    assertion_type = data.get("type")
    if not assertion_type:
        raise AssertionSpecError("assertion is missing required field 'type'")
    if assertion_type not in _REGISTRY:
        raise AssertionSpecError(
            f"unknown assertion type {assertion_type!r}; known types: {known_assertion_types()}"
        )
    for required in _REQUIRED_FIELDS[assertion_type]:
        if required not in data:
            raise AssertionSpecError(
                f"assertion of type {assertion_type!r} is missing required field {required!r}"
            )
    kwargs = {k: v for k, v in data.items() if k != "type"}
    if assertion_type == "json_has_keys" and "keys" in kwargs:
        keys = kwargs["keys"]
        if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
            raise AssertionSpecError("json_has_keys: 'keys' must be a list of strings")
        kwargs["keys"] = tuple(keys)
    if assertion_type == "one_of" and "values" in kwargs:
        values = kwargs["values"]
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise AssertionSpecError("one_of: 'values' must be a list of strings")
        kwargs["values"] = tuple(values)
    cls = _REGISTRY[assertion_type]
    try:
        instance: Assertion = cls(**kwargs)
    except TypeError as exc:
        raise AssertionSpecError(
            f"assertion of type {assertion_type!r} has invalid or unexpected fields: {exc}"
        ) from exc
    return instance
