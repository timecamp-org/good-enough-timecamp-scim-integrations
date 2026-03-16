import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from fetch_hibob import fetch_hibob_users, fetch_missing_supervisors, transform_hibob_employee
import fetch_hibob


@pytest.fixture(autouse=True)
def clear_cache():
    fetch_hibob.NOT_FOUND_EMPLOYEES_CACHE.clear()
    yield
    fetch_hibob.NOT_FOUND_EMPLOYEES_CACHE.clear()


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv('HIBOB_SERVICE_USER_ID', 'test_user_id')
    monkeypatch.setenv('HIBOB_SERVICE_USER_TOKEN', 'test_token')
    monkeypatch.setenv('HIBOB_EXCLUDE_FILTER', '')
    monkeypatch.setenv('HIBOB_EXCLUDED_DEPARTMENTS', '')
    monkeypatch.setenv('HIBOB_SUPERVISOR_RULE', '')
    monkeypatch.setenv('HIBOB_CUSTOM_FIELDS', '')


def make_hibob_employee(id, first_name, surname, email, department="Engineering",
                         title="Developer", reports_to_id="", reports_to_name="",
                         is_manager=False, start_date="2020-01-01",
                         status="Active", lifecycle_status="employed"):
    """Helper to create a HiBob employee dict."""
    emp = {
        "id": id,
        "firstName": first_name,
        "surname": surname,
        "fullName": f"{first_name} {surname}",
        "email": email,
        "work": {
            "department": department,
            "title": title,
            "isManager": is_manager,
            "startDate": start_date,
            "site": "HQ",
            "employeeIdInCompany": id,
        },
        "internal": {
            "status": status,
            "lifecycleStatus": lifecycle_status,
        }
    }
    if reports_to_id:
        emp["work"]["reportsTo"] = {"id": reports_to_id, "displayName": reports_to_name}
    else:
        emp["work"]["reportsTo"] = {}
    return emp


class TestTransformHibobEmployee:
    def test_basic_transform(self):
        emp = make_hibob_employee("1", "John", "Doe", "john@example.com",
                                  department="Engineering", title="Developer")
        user = transform_hibob_employee(emp)

        assert user["external_id"] == "1"
        assert user["name"] == "John Doe"
        assert user["email"] == "john@example.com"
        assert user["department"] == "Engineering"
        assert user["job_title"] == "Developer"
        assert user["status"] == "active"
        assert user["is_supervisor"] is False
        assert "raw_data" in user

    def test_supervisor_from_is_manager(self):
        emp = make_hibob_employee("1", "Jane", "Smith", "jane@example.com",
                                  is_manager=True)
        user = transform_hibob_employee(emp)
        assert user["is_supervisor"] is True

    def test_supervisor_from_custom_rule(self):
        emp = make_hibob_employee("1", "Jane", "Smith", "jane@example.com",
                                  is_manager=False)
        emp["work"]["customLevel"] = "Lead"

        user = transform_hibob_employee(emp, supervisor_field="work.customLevel",
                                        supervisor_value="Lead")
        assert user["is_supervisor"] is True

    def test_reports_to_extraction(self):
        emp = make_hibob_employee("1", "John", "Doe", "john@example.com",
                                  reports_to_id="mgr_1", reports_to_name="Jane Smith")
        user = transform_hibob_employee(emp)
        assert user["supervisor_id"] == "mgr_1"

    def test_missing_email_fields(self):
        emp = make_hibob_employee("1", "John", "Doe", "",
                                  department="", title="")
        user = transform_hibob_employee(emp)
        assert user["email"] == ""
        assert user["department"] == ""
        assert user["job_title"] == ""

    def test_fallback_name_from_parts(self):
        emp = {
            "id": "1",
            "firstName": "John",
            "surname": "Doe",
            "email": "john@example.com",
            "work": {"department": "IT"},
            "internal": {},
        }
        user = transform_hibob_employee(emp)
        assert user["name"] == "John Doe"

    def test_human_readable_department(self):
        """Test that humanReadable department is preferred over raw value."""
        emp = make_hibob_employee("1", "John", "Doe", "john@example.com",
                                  department="209192163")
        emp["humanReadable"] = {"work": {"department": "Engineering"}}
        user = transform_hibob_employee(emp)
        assert user["department"] == "Engineering"

    def test_reports_to_string_ignored(self):
        """Test that reportsTo as plain string (from humanReadable REPLACE) is ignored."""
        emp = make_hibob_employee("1", "John", "Doe", "john@example.com")
        emp["work"]["reportsTo"] = "Jane Smith"  # string from REPLACE mode
        user = transform_hibob_employee(emp)
        assert user["supervisor_id"] == ""


@patch('fetch_hibob.requests.post')
@patch('common.storage.save_json_file')
def test_fetch_hibob_users_basic(mock_save, mock_post, mock_env):
    """Test basic fetch with one active employee and one missing supervisor."""
    def side_effect(*args, **kwargs):
        json_body = kwargs.get('json', {})
        mock_resp = Mock()
        mock_resp.status_code = 200

        # Check if this is a filtered fetch (fetch_employees_by_ids) or main fetch
        filters = json_body.get('filters', [])
        is_id_fetch = any(
            f.get('fieldPath') == 'root.id' for f in filters
            if isinstance(f, dict)
        )

        if is_id_fetch:
            # Supervisor fetch
            values = []
            for f in filters:
                if f.get('fieldPath') == 'root.id':
                    values = f.get('values', [])

            if 'mgr_1' in values:
                mock_resp.json.return_value = {
                    "employees": [
                        make_hibob_employee("mgr_1", "Jane", "Manager", "jane@example.com",
                                            department="Engineering", title="Lead",
                                            is_manager=True, lifecycle_status="employed")
                    ]
                }
            else:
                mock_resp.json.return_value = {"employees": []}
        else:
            # Main fetch
            mock_resp.json.return_value = {
                "employees": [
                    make_hibob_employee("1", "John", "Doe", "john@example.com",
                                        department="Engineering", title="Developer",
                                        reports_to_id="mgr_1", reports_to_name="Jane Manager")
                ]
            }

        mock_resp.raise_for_status = Mock()
        return mock_resp

    mock_post.side_effect = side_effect

    fetch_hibob_users()

    assert mock_save.called
    saved_data = mock_save.call_args[0][0]

    assert "users" in saved_data
    assert len(saved_data["users"]) == 2  # 1 active + 1 inactive supervisor

    user1 = next(u for u in saved_data["users"] if u["external_id"] == "1")
    assert user1["name"] == "John Doe"
    assert user1["status"] == "active"
    assert user1["supervisor_id"] == "mgr_1"
    assert "raw_data" in user1

    supervisor = next(u for u in saved_data["users"] if u["external_id"] == "mgr_1")
    assert supervisor["name"] == "Jane Manager"
    assert supervisor["status"] == "inactive"
    assert "raw_data" in supervisor


@patch('fetch_hibob.requests.post')
@patch('common.storage.save_json_file')
def test_fetch_hibob_users_excludes_no_email(mock_save, mock_post, mock_env):
    """Test that employees without email are excluded."""
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = {
        "employees": [
            make_hibob_employee("1", "John", "Doe", "john@example.com"),
            make_hibob_employee("2", "No", "Email", ""),  # No email
        ]
    }
    mock_post.return_value = mock_resp

    fetch_hibob_users()

    saved_data = mock_save.call_args[0][0]
    assert len(saved_data["users"]) == 1
    assert saved_data["users"][0]["external_id"] == "1"


@patch('fetch_hibob.requests.post')
@patch('common.storage.save_json_file')
def test_fetch_hibob_users_excludes_future_hires(mock_save, mock_post, mock_env):
    """Test that future hires are excluded."""
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = {
        "employees": [
            make_hibob_employee("1", "John", "Doe", "john@example.com",
                                start_date="2020-01-01"),
            make_hibob_employee("2", "Future", "Hire", "future@example.com",
                                start_date="2099-01-01"),
        ]
    }
    mock_post.return_value = mock_resp

    fetch_hibob_users()

    saved_data = mock_save.call_args[0][0]
    assert len(saved_data["users"]) == 1
    assert saved_data["users"][0]["external_id"] == "1"


@patch('fetch_hibob.requests.post')
@patch('common.storage.save_json_file')
def test_fetch_hibob_users_excludes_departments(mock_save, mock_post, mock_env, monkeypatch):
    """Test that excluded departments are filtered out."""
    monkeypatch.setenv('HIBOB_EXCLUDED_DEPARTMENTS', 'Support,HR')

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = {
        "employees": [
            make_hibob_employee("1", "John", "Doe", "john@example.com",
                                department="Engineering"),
            make_hibob_employee("2", "Support", "User", "support@example.com",
                                department="Support"),
        ]
    }
    mock_post.return_value = mock_resp

    fetch_hibob_users()

    saved_data = mock_save.call_args[0][0]
    assert len(saved_data["users"]) == 1
    assert saved_data["users"][0]["external_id"] == "1"


@patch('fetch_hibob.requests.post')
@patch('common.storage.save_json_file')
def test_fetch_hibob_users_excludes_terminated(mock_save, mock_post, mock_env):
    """Test that terminated employees are excluded."""
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = {
        "employees": [
            make_hibob_employee("1", "John", "Doe", "john@example.com"),
            make_hibob_employee("2", "Term", "User", "term@example.com",
                                lifecycle_status="terminated"),
        ]
    }
    mock_post.return_value = mock_resp

    fetch_hibob_users()

    saved_data = mock_save.call_args[0][0]
    assert len(saved_data["users"]) == 1
    assert saved_data["users"][0]["external_id"] == "1"


@patch('fetch_hibob.requests.post')
def test_fetch_missing_supervisors_includes_raw_data(mock_post):
    """Test that missing supervisors include raw_data."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {
        "employees": [
            make_hibob_employee("mgr_1", "Supervisor", "User", "sup@example.com",
                                department="IT", title="Lead")
        ]
    }
    mock_post.return_value = mock_response

    headers = {}
    users = [
        {"external_id": "1", "supervisor_id": "mgr_1"}
    ]
    excluded_departments = []

    result = fetch_missing_supervisors(headers, users, excluded_departments, fetch_hibob.HIBOB_FIELDS)

    assert len(result) == 1
    supervisor = result[0]
    assert supervisor["external_id"] == "mgr_1"
    assert supervisor["status"] == "inactive"
    assert "raw_data" in supervisor
    assert supervisor["raw_data"]["id"] == "mgr_1"


@patch('fetch_hibob.requests.post')
def test_fetch_missing_supervisors_recursive(mock_post):
    """Test recursive supervisor fetching."""
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = Mock()

        json_body = kwargs.get('json', {})
        filters = json_body.get('filters', [])
        values = []
        for f in filters:
            if f.get('fieldPath') == 'root.id':
                values = f.get('values', [])

        if 'mgr_1' in values:
            mock_resp.json.return_value = {
                "employees": [
                    make_hibob_employee("mgr_1", "Mid", "Manager", "mid@example.com",
                                        reports_to_id="mgr_2", reports_to_name="Top Boss")
                ]
            }
        elif 'mgr_2' in values:
            mock_resp.json.return_value = {
                "employees": [
                    make_hibob_employee("mgr_2", "Top", "Boss", "top@example.com")
                ]
            }
        else:
            mock_resp.json.return_value = {"employees": []}

        return mock_resp

    mock_post.side_effect = side_effect

    headers = {}
    users = [
        {"external_id": "1", "supervisor_id": "mgr_1"}
    ]
    excluded_departments = []

    result = fetch_missing_supervisors(headers, users, excluded_departments, fetch_hibob.HIBOB_FIELDS)

    assert len(result) == 2
    ids = {s["external_id"] for s in result}
    assert ids == {"mgr_1", "mgr_2"}


@patch('fetch_hibob.requests.post')
def test_fetch_missing_supervisors_not_found_cache(mock_post):
    """Test that not-found employee IDs are cached."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"employees": []}
    mock_post.return_value = mock_response

    headers = {}
    users = [
        {"external_id": "1", "supervisor_id": "ghost_mgr"}
    ]
    excluded_departments = []

    result = fetch_missing_supervisors(headers, users, excluded_departments, fetch_hibob.HIBOB_FIELDS)

    assert len(result) == 0
    assert "ghost_mgr" in fetch_hibob.NOT_FOUND_EMPLOYEES_CACHE

    # Second call should not make API request
    mock_post.reset_mock()
    result2 = fetch_missing_supervisors(headers, users, excluded_departments, fetch_hibob.HIBOB_FIELDS)
    assert len(result2) == 0
    mock_post.assert_not_called()
