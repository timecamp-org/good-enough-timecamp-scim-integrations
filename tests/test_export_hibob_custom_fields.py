from unittest.mock import Mock, patch

import pytest

import export_hibob_custom_fields
from export_hibob_custom_fields import fetch_hibob_custom_fields, is_custom_hibob_field


@pytest.fixture(autouse=True)
def reset_logger():
    export_hibob_custom_fields.logger = None
    yield
    export_hibob_custom_fields.logger = None


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("HIBOB_SERVICE_USER_ID", "test_user_id")
    monkeypatch.setenv("HIBOB_SERVICE_USER_TOKEN", "test_token")


def test_is_custom_hibob_field_matches_supported_patterns():
    assert is_custom_hibob_field({"id": "work.custom.field_123", "jsonPath": "work.custom.field_123"}) is True
    assert is_custom_hibob_field({"id": "custom.category_1.field_2", "jsonPath": "custom.category_1.field_2"}) is True
    assert is_custom_hibob_field({"id": "work.department", "jsonPath": "work.department"}) is False


@patch("export_hibob_custom_fields.save_json_file")
@patch("export_hibob_custom_fields.requests.get")
def test_fetch_hibob_custom_fields_exports_custom_only(mock_get, mock_save, mock_env):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = [
        {
            "id": "work.department",
            "jsonPath": "work.department",
            "name": "Department",
            "category": "work",
            "categoryDisplayName": "Work",
            "type": "list",
        },
        {
            "id": "work.custom.field_123",
            "jsonPath": "work.custom.field_123",
            "name": "Favorite Color",
            "category": "work",
            "categoryDisplayName": "Work",
            "type": "string",
        },
        {
            "id": "custom.category_1.field_2",
            "jsonPath": "custom.category_1.field_2",
            "name": "Access Level",
            "category": "category_1",
            "categoryDisplayName": "Access",
            "type": "list",
        },
    ]
    mock_get.return_value = mock_response

    result = fetch_hibob_custom_fields()

    mock_get.assert_called_once()
    request_headers = mock_get.call_args.kwargs["headers"]
    assert request_headers["Authorization"].startswith("Basic ")

    mock_save.assert_called_once()
    saved_payload, saved_path = mock_save.call_args[0]

    assert saved_path == "var/hibob_custom_fields.json"
    assert result["total_fields_count"] == 3
    assert result["custom_fields_count"] == 2
    assert saved_payload["custom_fields_count"] == 2
    assert [field["id"] for field in saved_payload["custom_fields"]] == [
        "custom.category_1.field_2",
        "work.custom.field_123",
    ]
    assert saved_payload["custom_field_categories"] == {
        "Access": 1,
        "Work": 1,
    }
