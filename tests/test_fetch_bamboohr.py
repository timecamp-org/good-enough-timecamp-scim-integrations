import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from fetch_bamboohr import fetch_bamboo_users, fetch_missing_supervisors
import fetch_bamboohr

@pytest.fixture(autouse=True)
def clear_cache():
    fetch_bamboohr.NOT_FOUND_EMPLOYEES_CACHE.clear()
    yield
    fetch_bamboohr.NOT_FOUND_EMPLOYEES_CACHE.clear()

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv('BAMBOOHR_SUBDOMAIN', 'test_subdomain')
    monkeypatch.setenv('BAMBOOHR_API_KEY', 'test_key')
    monkeypatch.setenv('BAMBOOHR_EXCLUDE_FILTER', '')
    monkeypatch.setenv('BAMBOOHR_EXCLUDED_DEPARTMENTS', '')
    monkeypatch.setenv('BAMBOOHR_SUPERVISOR_RULE', '')

@patch('fetch_bamboohr.requests.post')
@patch('common.storage.save_json_file')
def test_fetch_bamboo_users_includes_raw_data(mock_save, mock_post, mock_env):
    # Define side effect for mock_post to return different data based on context
    def side_effect(*args, **kwargs):
        json_body = kwargs.get('json', {})
        mock_resp = Mock()
        mock_resp.status_code = 200
        
        # Check if it's fetching by ID (has filters with 'match': 'any') or main fetch
        if json_body.get('filters', {}).get('match') == 'any':
            # This is fetch_missing_supervisors call
            # Let's say we find the supervisor if ID is 2
            filters = json_body['filters']['filters']
            # Simplistic check if we are looking for '2'
            seeking_2 = any(f.get('value') == '2' for f in filters)
            
            if seeking_2:
                mock_resp.json.return_value = {
                    "data": [{
                        "employeeNumber": "2",
                        "name": "Supervisor User",
                        "email": "sup@example.com",
                        "jobInformationDepartment": "IT",
                        "jobInformationDivision": "Tech",
                        "jobInformationJobTitle": "Manager",
                        "supervisorId": "",
                        "employmentStatus": "Active",
                        "status": "Active"
                    }],
                    "pagination": {"next_page": None}
                }
            else:
                 mock_resp.json.return_value = {"data": [], "pagination": {"next_page": None}}

        else:
            # Main fetch
            mock_resp.json.return_value = {
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
        return mock_resp

    mock_post.side_effect = side_effect

    fetch_bamboo_users()

    # Verify save_json_file was called
    assert mock_save.called
    saved_data = mock_save.call_args[0][0]
    
    # Check if raw_data is included
    assert "users" in saved_data
    # Should have 2 users: 1 active, 1 inactive supervisor
    assert len(saved_data["users"]) == 2
    
    user1 = next(u for u in saved_data["users"] if u["external_id"] == "1")
    assert "raw_data" in user1
    assert user1["raw_data"]["employeeNumber"] == "1"
    
    user2 = next(u for u in saved_data["users"] if u["external_id"] == "2")
    assert "raw_data" in user2
    assert user2["raw_data"]["employeeNumber"] == "2"

@patch('fetch_bamboohr.requests.post')
def test_fetch_missing_supervisors_includes_raw_data(mock_post):
    # Mock response for fetch_employees_by_ids
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "employeeNumber": "2",
                "name": "Supervisor",
                "email": "sup@example.com",
                "jobInformationDepartment": "IT",
                "jobInformationDivision": "Tech",
                "jobInformationJobTitle": "Lead",
                "supervisorId": "",
                "employmentStatus": "Active",
                "hireDate": "2019-01-01",
                "status": "Active"
            }
        ]
    }
    mock_post.return_value = mock_response

    headers = {}
    users = [
        {"external_id": "1", "supervisor_id": "2"}
    ]
    excluded_departments = []

    # Should fetch supervisor 2
    result = fetch_missing_supervisors("subdomain", headers, users, excluded_departments)

    assert len(result) == 1
    supervisor = result[0]
    assert supervisor["external_id"] == "2"
    assert "raw_data" in supervisor
    assert supervisor["raw_data"]["employeeNumber"] == "2"
    assert supervisor["raw_data"]["name"] == "Supervisor"
