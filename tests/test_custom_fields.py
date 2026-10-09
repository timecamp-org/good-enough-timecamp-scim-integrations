"""
Tests for the shared TimeCamp user custom field helpers.
"""
import pytest

from common.custom_fields import (
    custom_field_values_equal,
    extract_custom_fields,
    is_valid_number,
    normalize_custom_field_value,
    normalize_custom_fields,
    parse_custom_field_mapping,
)


class TestParseCustomFieldMapping:
    def test_parses_pairs_and_strips_whitespace(self):
        mapping = parse_custom_field_mapping(
            " title : Job Position , profile.costCenter:Cost Center ",
            "SETTING",
        )

        assert mapping == [("title", "Job Position"), ("profile.costCenter", "Cost Center")]

    def test_timecamp_name_can_contain_colons(self):
        assert parse_custom_field_mapping("code:Code: Internal", "SETTING") == [("code", "Code: Internal")]

    @pytest.mark.parametrize("value", [None, "", "   ", ",,"])
    def test_empty_value_returns_no_mapping(self, value):
        assert parse_custom_field_mapping(value, "SETTING") == []

    @pytest.mark.parametrize("entry", ["title", ":Job Position", "title:", "title: "])
    def test_rejects_incomplete_entries(self, entry):
        with pytest.raises(ValueError, match="SETTING entry"):
            parse_custom_field_mapping(entry, "SETTING")

    def test_rejects_two_sources_for_one_timecamp_field(self):
        with pytest.raises(ValueError, match="more than one source field"):
            parse_custom_field_mapping("title:Job Position,position:job position", "SETTING")

    def test_one_source_can_feed_many_timecamp_fields(self):
        assert parse_custom_field_mapping("title:Job Position,title:Role", "SETTING") == [
            ("title", "Job Position"),
            ("title", "Role"),
        ]


class TestNormalizeCustomFieldValue:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, None),
            ("", None),
            ("   ", None),
            ("  Developer  ", "Developer"),
            (True, "true"),
            (False, "false"),
            (42, "42"),
            (5.0, "5"),
            (2.5, "2.5"),
            (["Team A", "", None, "Team B"], "Team A, Team B"),
            ([], None),
            ({"b": 1, "a": "x"}, '{"a": "x", "b": 1}'),
        ],
    )
    def test_converts_source_values(self, value, expected):
        assert normalize_custom_field_value(value) == expected


class TestNormalizeCustomFields:
    def test_missing_object_returns_none(self):
        assert normalize_custom_fields(None) is None

    def test_normalizes_names_and_values(self):
        assert normalize_custom_fields({" Job Position ": " Developer ", "Cost Center": "", " ": "x"}) == {
            "Job Position": "Developer",
            "Cost Center": None,
        }

    def test_empty_object_is_kept(self):
        assert normalize_custom_fields({}) == {}

    def test_rejects_non_object(self):
        with pytest.raises(ValueError, match="custom_fields must be an object"):
            normalize_custom_fields(["Job Position"])


def test_extract_custom_fields_reads_each_mapped_source_field():
    record = {"title": "Developer", "costCenter": 1200, "empty": ""}

    custom_fields = extract_custom_fields(
        record,
        [("title", "Job Position"), ("costCenter", "Cost Center"), ("empty", "Notes"), ("missing", "Team")],
        lambda data, field: data.get(field),
    )

    assert custom_fields == {
        "Job Position": "Developer",
        "Cost Center": "1200",
        "Notes": None,
        "Team": None,
    }


@pytest.mark.parametrize("value", ["0", "-1", "+3", "2.5", ".5", "5.", "1e3", "1E-2"])
def test_is_valid_number_accepts_numbers(value):
    assert is_valid_number(value)


@pytest.mark.parametrize("value", ["", "abc", "1,5", "nan", "inf", "1_000", "1 2"])
def test_is_valid_number_rejects_other_values(value):
    assert not is_valid_number(value)


class TestCustomFieldValuesEqual:
    def test_strings_must_match_exactly(self):
        assert custom_field_values_equal("Developer", "Developer", "string")
        assert not custom_field_values_equal("Developer", "developer", "string")

    def test_numbers_compare_by_value(self):
        assert custom_field_values_equal("75", "75.0", "number")
        assert not custom_field_values_equal("75", "76", "number")

    def test_number_text_is_not_compared_by_value_for_string_fields(self):
        assert not custom_field_values_equal("75", "75.0", "string")

    def test_empty_values(self):
        assert custom_field_values_equal(None, None, "string")
        assert not custom_field_values_equal(None, "Developer", "string")
        assert not custom_field_values_equal("Developer", None, "string")
