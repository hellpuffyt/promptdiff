"""Tests for every model-free assertion type, in both directions."""

from __future__ import annotations

import pytest

from promptdiff.assertions import (
    AssertionSpecError,
    ContainsAssertion,
    IsValidJsonAssertion,
    JsonHasKeysAssertion,
    JsonSchemaAssertion,
    MatchesRegexAssertion,
    MaxLengthAssertion,
    NotContainsAssertion,
    OneOfAssertion,
    StartsWithAssertion,
    known_assertion_types,
    parse_assertion,
)


class TestContains:
    def test_fires_when_substring_present(self) -> None:
        result = ContainsAssertion(value="hello").check("well hello there")
        assert result.passed is True
        assert result.assertion_type == "contains"

    def test_does_not_fire_when_absent(self) -> None:
        result = ContainsAssertion(value="goodbye").check("well hello there")
        assert result.passed is False

    def test_case_insensitive(self) -> None:
        result = ContainsAssertion(value="HELLO", case_sensitive=False).check("well hello there")
        assert result.passed is True

    def test_case_sensitive_by_default_fails_on_mismatch(self) -> None:
        result = ContainsAssertion(value="HELLO").check("well hello there")
        assert result.passed is False


class TestNotContains:
    def test_fires_when_absent(self) -> None:
        result = NotContainsAssertion(value="goodbye").check("well hello there")
        assert result.passed is True

    def test_does_not_fire_when_present(self) -> None:
        result = NotContainsAssertion(value="hello").check("well hello there")
        assert result.passed is False

    def test_case_insensitive(self) -> None:
        result = NotContainsAssertion(value="HELLO", case_sensitive=False).check("well hello there")
        assert result.passed is False


class TestMatchesRegex:
    def test_fires_on_match(self) -> None:
        result = MatchesRegexAssertion(pattern=r"^\d{4}-\d{2}-\d{2}$").check("2026-08-30")
        assert result.passed is True

    def test_does_not_fire_without_match(self) -> None:
        result = MatchesRegexAssertion(pattern=r"^\d{4}-\d{2}-\d{2}$").check("August 30, 2026")
        assert result.passed is False

    def test_case_insensitive_flag(self) -> None:
        result = MatchesRegexAssertion(pattern="hello", flags="i").check("HELLO world")
        assert result.passed is True

    def test_multiline_flag(self) -> None:
        result = MatchesRegexAssertion(pattern="^line2$", flags="m").check("line1\nline2\nline3")
        assert result.passed is True

    def test_dotall_flag(self) -> None:
        result = MatchesRegexAssertion(pattern="a.b", flags="s").check("a\nb")
        assert result.passed is True

    def test_unknown_flag_raises(self) -> None:
        with pytest.raises(AssertionSpecError):
            MatchesRegexAssertion(pattern="x", flags="z").check("x")

    def test_invalid_pattern_raises(self) -> None:
        with pytest.raises(AssertionSpecError):
            MatchesRegexAssertion(pattern="(unclosed").check("x")


class TestIsValidJson:
    def test_fires_on_valid_json(self) -> None:
        result = IsValidJsonAssertion().check('{"a": 1}')
        assert result.passed is True

    def test_does_not_fire_on_invalid_json(self) -> None:
        result = IsValidJsonAssertion().check('{"a": 1')
        assert result.passed is False

    def test_valid_json_array(self) -> None:
        result = IsValidJsonAssertion().check("[1, 2, 3]")
        assert result.passed is True

    def test_plain_text_is_not_json(self) -> None:
        result = IsValidJsonAssertion().check("hello there")
        assert result.passed is False


class TestJsonHasKeys:
    def test_fires_when_all_keys_present(self) -> None:
        result = JsonHasKeysAssertion(keys=("name", "age")).check('{"name": "Jo", "age": 1}')
        assert result.passed is True

    def test_does_not_fire_when_key_missing(self) -> None:
        result = JsonHasKeysAssertion(keys=("name", "age")).check('{"name": "Jo"}')
        assert result.passed is False
        assert "age" in result.message

    def test_does_not_fire_on_invalid_json(self) -> None:
        result = JsonHasKeysAssertion(keys=("name",)).check("not json")
        assert result.passed is False

    def test_does_not_fire_on_json_array(self) -> None:
        result = JsonHasKeysAssertion(keys=("name",)).check("[1, 2]")
        assert result.passed is False

    def test_extra_keys_still_pass(self) -> None:
        result = JsonHasKeysAssertion(keys=("name",)).check('{"name": "Jo", "extra": true}')
        assert result.passed is True


class TestJsonSchema:
    SCHEMA = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
    }

    def test_fires_when_valid(self) -> None:
        result = JsonSchemaAssertion(schema=self.SCHEMA).check('{"name": "Jo", "age": 5}')
        assert result.passed is True

    def test_does_not_fire_on_wrong_type(self) -> None:
        result = JsonSchemaAssertion(schema=self.SCHEMA).check('{"name": "Jo", "age": "five"}')
        assert result.passed is False

    def test_does_not_fire_on_missing_required(self) -> None:
        result = JsonSchemaAssertion(schema=self.SCHEMA).check('{"name": "Jo"}')
        assert result.passed is False

    def test_does_not_fire_on_invalid_json(self) -> None:
        result = JsonSchemaAssertion(schema=self.SCHEMA).check("not json")
        assert result.passed is False

    def test_invalid_schema_raises_at_construction(self) -> None:
        with pytest.raises(AssertionSpecError):
            JsonSchemaAssertion(schema={"type": "not-a-real-type"})


class TestMaxLength:
    def test_fires_when_within_limit(self) -> None:
        result = MaxLengthAssertion(value=10).check("short")
        assert result.passed is True

    def test_does_not_fire_when_over_limit(self) -> None:
        result = MaxLengthAssertion(value=3).check("too long")
        assert result.passed is False

    def test_exact_length_passes(self) -> None:
        result = MaxLengthAssertion(value=5).check("12345")
        assert result.passed is True

    def test_negative_value_raises(self) -> None:
        with pytest.raises(AssertionSpecError):
            MaxLengthAssertion(value=-1)


class TestStartsWith:
    def test_fires_on_prefix(self) -> None:
        result = StartsWithAssertion(value="Hello").check("Hello world")
        assert result.passed is True

    def test_does_not_fire_without_prefix(self) -> None:
        result = StartsWithAssertion(value="Hello").check("world, Hello")
        assert result.passed is False

    def test_case_insensitive(self) -> None:
        result = StartsWithAssertion(value="hello", case_sensitive=False).check("HELLO world")
        assert result.passed is True


class TestOneOf:
    def test_fires_on_exact_match(self) -> None:
        result = OneOfAssertion(values=("positive", "negative", "neutral")).check("positive")
        assert result.passed is True

    def test_does_not_fire_when_not_in_set(self) -> None:
        result = OneOfAssertion(values=("positive", "negative", "neutral")).check("mixed")
        assert result.passed is False

    def test_strips_whitespace_by_default(self) -> None:
        result = OneOfAssertion(values=("positive",)).check("  positive\n")
        assert result.passed is True

    def test_no_strip_when_disabled(self) -> None:
        result = OneOfAssertion(values=("positive",), strip=False).check("  positive\n")
        assert result.passed is False

    def test_case_insensitive(self) -> None:
        result = OneOfAssertion(values=("positive",), case_sensitive=False).check("POSITIVE")
        assert result.passed is True

    def test_punctuation_causes_mismatch(self) -> None:
        result = OneOfAssertion(values=("positive",)).check("Positive.")
        assert result.passed is False


class TestParseAssertion:
    def test_parses_contains(self) -> None:
        a = parse_assertion({"type": "contains", "value": "x"})
        assert isinstance(a, ContainsAssertion)
        assert a.value == "x"

    def test_parses_is_valid_json_with_no_extra_fields(self) -> None:
        a = parse_assertion({"type": "is_valid_json"})
        assert isinstance(a, IsValidJsonAssertion)

    def test_parses_json_has_keys_list_becomes_tuple(self) -> None:
        a = parse_assertion({"type": "json_has_keys", "keys": ["a", "b"]})
        assert isinstance(a, JsonHasKeysAssertion)
        assert a.keys == ("a", "b")

    def test_parses_one_of_list_becomes_tuple(self) -> None:
        a = parse_assertion({"type": "one_of", "values": ["a", "b"]})
        assert isinstance(a, OneOfAssertion)
        assert a.values == ("a", "b")

    def test_missing_type_raises(self) -> None:
        with pytest.raises(AssertionSpecError, match="type"):
            parse_assertion({"value": "x"})

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(AssertionSpecError, match="unknown assertion type"):
            parse_assertion({"type": "nonexistent"})

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(AssertionSpecError, match="value"):
            parse_assertion({"type": "contains"})

    def test_not_a_mapping_raises(self) -> None:
        with pytest.raises(AssertionSpecError, match="mapping"):
            parse_assertion("not a dict")  # type: ignore[arg-type]

    def test_json_has_keys_rejects_non_list_keys(self) -> None:
        with pytest.raises(AssertionSpecError, match="keys"):
            parse_assertion({"type": "json_has_keys", "keys": "not-a-list"})

    def test_json_has_keys_rejects_non_string_items(self) -> None:
        with pytest.raises(AssertionSpecError, match="keys"):
            parse_assertion({"type": "json_has_keys", "keys": [1, 2]})

    def test_one_of_rejects_non_list_values(self) -> None:
        with pytest.raises(AssertionSpecError, match="values"):
            parse_assertion({"type": "one_of", "values": "not-a-list"})

    def test_unexpected_field_raises(self) -> None:
        with pytest.raises(AssertionSpecError):
            parse_assertion({"type": "contains", "value": "x", "bogus_field": 1})

    def test_known_assertion_types_is_sorted_and_complete(self) -> None:
        types = known_assertion_types()
        assert types == sorted(types)
        expected = {
            "contains",
            "not_contains",
            "matches_regex",
            "is_valid_json",
            "json_has_keys",
            "json_schema",
            "max_length",
            "starts_with",
            "one_of",
        }
        assert set(types) == expected

    def test_describe_is_human_readable(self) -> None:
        a = parse_assertion({"type": "contains", "value": "x"})
        assert "contains" in a.describe()
