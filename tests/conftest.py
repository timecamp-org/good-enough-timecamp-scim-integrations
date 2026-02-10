"""
Pytest configuration and shared fixtures for TimeCamp SCIM Integration tests.
"""
import os
import json
import pytest
from typing import Dict, Any
from unittest.mock import MagicMock, Mock
from pathlib import Path


# Test data directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Return the fixtures directory path."""
    return FIXTURES_DIR


@pytest.fixture
def sample_users():
    """Load and return sample users from fixture file."""
    with open(FIXTURES_DIR / "users_sample.json", "r") as f:
        return json.load(f)


@pytest.fixture
def sample_timecamp_users():
    """Load and return sample prepared TimeCamp users from fixture file."""
    with open(FIXTURES_DIR / "timecamp_users_sample.json", "r") as f:
        return json.load(f)


@pytest.fixture
def sample_vacation_data():
    """Load and return sample vacation data from fixture file."""
    with open(FIXTURES_DIR / "vacation_sample.json", "r") as f:
        return json.load(f)


@pytest.fixture
def azure_api_responses():
    """Load and return mock Azure API responses."""
    with open(FIXTURES_DIR / "azure_api_responses.json", "r") as f:
        return json.load(f)


@pytest.fixture
def timecamp_api_responses():
    """Load and return mock TimeCamp API responses."""
    with open(FIXTURES_DIR / "timecamp_api_responses.json", "r") as f:
        return json.load(f)


@pytest.fixture
def mock_timecamp_config():
    """Create a mock TimeCamp configuration object."""
    from common.utils import TimeCampConfig
    
    return TimeCampConfig(
        api_key="test_api_key_12345",
        domain="app.timecamp.com",
        root_group_id=100,
        ignored_user_ids={9999},
        show_external_id=False,
        skip_departments="",
        use_supervisor_groups=False,
        use_department_groups=True,
        disable_new_users=False,
        disable_external_id_sync=False,
        disable_additional_email_sync=False,
        update_email_on_external_id=False,
        disable_manual_user_updates=False,
        disable_user_deactivation=False,
        disable_group_updates=False,
        disable_role_updates=False,
        disable_groups_creation=False,
        use_job_title_name_users=False,
        use_job_title_name_groups=False,
        replace_email_domain="",
        use_is_supervisor_role=False,
        disabled_users_group_id=0,
        exclude_regex="",
        change_groups_regex="",
        prepare_transform_config="",
        remove_empty_groups=False,
        ssl_verify=True
    )


@pytest.fixture
def mock_timecamp_api(timecamp_api_responses):
    """Create a mock TimeCamp API client."""
    from common.api import TimeCampAPI
    
    api = MagicMock(spec=TimeCampAPI)
    
    # Mock common API methods
    api.get_users.return_value = timecamp_api_responses["users"]
    api.get_groups.return_value = timecamp_api_responses["groups"]
    api.get_day_types.return_value = timecamp_api_responses["day_types"]
    api.add_user.return_value = timecamp_api_responses["add_user_response"]
    api.add_group.return_value = timecamp_api_responses["add_group_response"]["group_id"]
    api.update_user.return_value = None
    api.update_user_setting.return_value = None
    api.set_additional_email.return_value = None
    api.get_additional_emails.return_value = {}
    api.get_external_ids.return_value = {}
    api.get_manually_added_statuses.return_value = {}
    api.are_users_enabled.return_value = {}
    api.get_user_roles.return_value = timecamp_api_responses["people_picker"]["groups"]
    api.add_vacation.return_value = None
    
    return api


@pytest.fixture
def mock_azure_token_manager(azure_api_responses):
    """Create a mock Azure Token Manager."""
    from fetch_azuread import AzureTokenManager
    
    manager = MagicMock(spec=AzureTokenManager)
    manager.get_valid_token.return_value = (
        azure_api_responses["token_response"]["access_token"],
        True
    )
    
    return manager


@pytest.fixture
def mock_requests_get(mocker, azure_api_responses):
    """Mock requests.get for Azure AD API calls."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = azure_api_responses["users_page_1"]
    
    mock_get = mocker.patch("requests.get", return_value=mock_response)
    return mock_get


@pytest.fixture
def mock_requests_post(mocker, azure_api_responses):
    """Mock requests.post for token requests."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = azure_api_responses["token_response"]
    
    mock_post = mocker.patch("requests.post", return_value=mock_response)
    return mock_post


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    env_vars = {
        # TimeCamp configuration
        "TIMECAMP_API_KEY": "test_api_key",
        "TIMECAMP_DOMAIN": "app.timecamp.com",
        "TIMECAMP_ROOT_GROUP_ID": "100",
        "TIMECAMP_IGNORED_USER_IDS": "9999",
        "TIMECAMP_SHOW_EXTERNAL_ID": "false",
        "TIMECAMP_SKIP_DEPARTMENTS": "",
        "TIMECAMP_USE_SUPERVISOR_GROUPS": "false",
        "TIMECAMP_USE_DEPARTMENT_GROUPS": "true",
        "TIMECAMP_DISABLE_NEW_USERS": "false",
        "TIMECAMP_DISABLE_EXTERNAL_ID_SYNC": "false",
        "TIMECAMP_DISABLE_ADDITIONAL_EMAIL_SYNC": "false",
        "TIMECAMP_UPDATE_EMAIL_ON_EXTERNAL_ID": "false",
        "TIMECAMP_DISABLE_MANUAL_USER_UPDATES": "false",
        "TIMECAMP_DISABLE_USER_DEACTIVATION": "false",
        "TIMECAMP_DISABLE_GROUP_UPDATES": "false",
        "TIMECAMP_DISABLE_ROLE_UPDATES": "false",
        "TIMECAMP_DISABLE_GROUPS_CREATION": "false",
        "TIMECAMP_USE_JOB_TITLE_NAME_USERS": "false",
        "TIMECAMP_USE_JOB_TITLE_NAME_GROUPS": "false",
        "TIMECAMP_REPLACE_EMAIL_DOMAIN": "",
        "TIMECAMP_USE_IS_SUPERVISOR_ROLE": "false",
        "TIMECAMP_DISABLED_USERS_GROUP_ID": "0",
        "TIMECAMP_PREPARE_TRANSFORM_CONFIG": "",
        "TIMECAMP_SSL_VERIFY": "false",
        
        # Azure AD configuration
        "AZURE_TENANT_ID": "test-tenant-id",
        "AZURE_CLIENT_ID": "test-client-id",
        "AZURE_CLIENT_SECRET": "test-client-secret",
        "AZURE_SCIM_ENDPOINT": "https://graph.microsoft.com/v1.0/users",
        "AZURE_PREFER_REAL_EMAIL": "false",
        "AZURE_FILTER_GROUPS": "",
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary directory for test output files."""
    var_dir = tmp_path / "var"
    var_dir.mkdir()
    return var_dir


@pytest.fixture
def mock_storage_functions(mocker, temp_output_dir):
    """Mock storage functions to use temporary directory."""
    def mock_save_json_file(data, filename, **kwargs):
        """Mock save_json_file to write to temp directory."""
        path = temp_output_dir / Path(filename).name
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, **kwargs)
    
    def mock_load_json_file(filename):
        """Mock load_json_file to read from temp directory."""
        path = temp_output_dir / Path(filename).name
        with open(path, 'r') as f:
            return json.load(f)
    
    def mock_file_exists(filename):
        """Mock file_exists to check temp directory."""
        path = temp_output_dir / Path(filename).name
        return path.exists()
    
    mocker.patch("common.storage.save_json_file", side_effect=mock_save_json_file)
    mocker.patch("common.storage.load_json_file", side_effect=mock_load_json_file)
    mocker.patch("common.storage.file_exists", side_effect=mock_file_exists)
    
    return {
        "save_json_file": mock_save_json_file,
        "load_json_file": mock_load_json_file,
        "file_exists": mock_file_exists,
        "temp_dir": temp_output_dir
    }


@pytest.fixture
def sample_user_with_supervisor():
    """Create a sample user with supervisor relationship."""
    return {
        "external_id": "user-123",
        "name": "John Doe",
        "email": "john.doe@example.com",
        "department": "Engineering",
        "job_title": "Software Engineer",
        "status": "active",
        "supervisor_id": "supervisor-456"
    }


@pytest.fixture
def sample_supervisor():
    """Create a sample supervisor user."""
    return {
        "external_id": "supervisor-456",
        "name": "Jane Smith",
        "email": "jane.smith@example.com",
        "department": "Engineering",
        "job_title": "Engineering Manager",
        "status": "active",
        "supervisor_id": ""
    }


@pytest.fixture
def mock_logger(mocker):
    """Mock logger to prevent actual logging during tests."""
    return mocker.patch("common.logger.setup_logger")


# Helper functions for tests

def create_mock_response(status_code=200, json_data=None, raise_for_status=False):
    """Create a mock requests.Response object."""
    mock_resp = Mock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    mock_resp.text = json.dumps(json_data or {})
    
    if raise_for_status:
        mock_resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        mock_resp.raise_for_status.return_value = None
    
    return mock_resp


def assert_api_called_with(mock_api, method_name, *args, **kwargs):
    """Helper to assert API method was called with specific arguments."""
    method = getattr(mock_api, method_name)
    method.assert_called()
    
    if args or kwargs:
        method.assert_called_with(*args, **kwargs)

