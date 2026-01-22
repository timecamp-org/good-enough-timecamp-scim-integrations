import pytest
import json
import logging
from unittest.mock import Mock, patch
from fetch_bamboohr import fetch_bamboo_users

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv('BAMBOOHR_SUBDOMAIN', 'test_subdomain')
    monkeypatch.setenv('BAMBOOHR_API_KEY', 'test_key')
    monkeypatch.setenv('DEBUG', 'true')  # Enable debug mode
    monkeypatch.setenv('DISABLE_FILE_LOGGING', 'true') # Disable file logging for test

@patch('fetch_bamboohr.requests.post')
@patch('common.storage.save_json_file')
def test_fetch_bamboo_users_debug_log(mock_save, mock_post, mock_env, caplog):
    caplog.set_level(logging.DEBUG)
    
    # Mock API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "employeeNumber": "1",
                "name": "Test User",
                "email": "test@example.com",
                "jobInformationDepartment": "IT",
                "jobInformationDivision": "Tech",
                "jobInformationJobTitle": "Dev",
                "supervisorId": "2",
                "employmentStatus": "Active",
                "hireDate": "2020-01-01",
                "status": "Active"
            }
        ],
        "pagination": {"next_page": None}
    }
    mock_post.return_value = mock_response

    fetch_bamboo_users()

    # Look for the debug log
    debug_records = [r for r in caplog.records if "Processed user:" in r.message]
    assert len(debug_records) > 0
    print("\nExample Log Record:\n")
    print(debug_records[0].message)
