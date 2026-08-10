import json
from unittest.mock import Mock, patch

import pytest
import requests

import fetch_okta
from fetch_okta import (
    OktaClient,
    collect_group_member_ids,
    fetch_missing_supervisors,
    fetch_okta_users,
    normalize_org_url,
    resolve_supervisor_ids,
    transform_okta_user_to_schema,
)


@pytest.fixture(autouse=True)
def clear_cache():
    fetch_okta.NOT_FOUND_USERS_CACHE.clear()
    yield
    fetch_okta.NOT_FOUND_USERS_CACHE.clear()


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("OKTA_ORG_URL", "https://example.okta.com")
    monkeypatch.setenv("OKTA_API_TOKEN", "test-token")
    monkeypatch.setenv("OKTA_USER_STATUSES", "ACTIVE")
    monkeypatch.setenv("OKTA_FILTER_GROUPS", "")
    monkeypatch.setenv("OKTA_FILTER_GROUP_IDS", "")
    monkeypatch.setenv("OKTA_SUPERVISOR_GROUPS", "")
    monkeypatch.setenv("OKTA_EXCLUDED_DEPARTMENTS", "")
    monkeypatch.setenv("OKTA_EXTERNAL_ID_FIELD", "id")
    monkeypatch.setenv("OKTA_EMAIL_FIELD", "email")
    monkeypatch.setenv("OKTA_NAME_FIELD", "displayName")
    monkeypatch.setenv("OKTA_DEPARTMENT_FIELD", "department")
    monkeypatch.setenv("OKTA_JOB_TITLE_FIELD", "title")
    monkeypatch.setenv("OKTA_SUPERVISOR_ID_FIELD", "managerId")
    monkeypatch.setenv("OKTA_SUPERVISOR_MATCH_FIELD", "")
    monkeypatch.setenv("OKTA_SUPERVISOR_RULE", "")
    monkeypatch.setenv("OKTA_MAX_HIERARCHY_ROOTS", "0")


def make_okta_user(
    user_id,
    email,
    display_name="Test User",
    department="Engineering",
    title="Developer",
    manager_id="",
    status="ACTIVE",
    extra_profile=None,
):
    profile = {
        "email": email,
        "login": email,
        "displayName": display_name,
        "firstName": display_name.split(" ")[0],
        "lastName": display_name.split(" ")[-1],
        "department": department,
        "title": title,
    }
    if manager_id:
        profile["managerId"] = manager_id
    if extra_profile:
        profile.update(extra_profile)

    return {
        "id": user_id,
        "status": status,
        "profile": profile,
    }


def mock_response(data, links=None, status_code=200):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = data
    response.links = links or {}

    def raise_for_status():
        if status_code >= 400:
            error = requests.exceptions.HTTPError()
            error.response = response
            raise error

    response.raise_for_status.side_effect = raise_for_status
    return response


def get_logged_okta_validation(caplog):
    """Parse the most recent structured Okta validation log event."""
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("Okta validation: ")
    ]
    assert messages
    return json.loads(messages[-1].removeprefix("Okta validation: "))


def test_normalize_org_url_adds_scheme_and_strips_slash():
    assert normalize_org_url("example.okta.com/") == "https://example.okta.com"
    assert normalize_org_url("https://example.okta.com/") == "https://example.okta.com"


def test_transform_okta_user_defaults():
    okta_user = make_okta_user(
        "00u1",
        "USER@example.com",
        display_name="Jane Doe",
        department="Product",
        title="Manager",
        manager_id="00u-manager",
    )

    user = transform_okta_user_to_schema(okta_user)

    assert user["external_id"] == "00u1"
    assert user["name"] == "Jane Doe"
    assert user["email"] == "user@example.com"
    assert user["department"] == "Product"
    assert user["job_title"] == "Manager"
    assert user["status"] == "active"
    assert user["supervisor_id"] == "00u-manager"
    assert user["is_supervisor"] is False
    assert user["raw_data"] == okta_user


def test_transform_okta_user_custom_fields_and_supervisor_rule():
    okta_user = make_okta_user(
        "00u1",
        "jane@example.com",
        extra_profile={
            "primaryEmail": "jane.primary@example.com",
            "orgUnit": "R&D",
            "position": "Lead",
            "managerExternalId": "mgr-1",
            "timecampSupervisor": "yes",
        },
    )
    field_config = {
        "email": "primaryEmail",
        "department": "orgUnit",
        "job_title": "position",
        "supervisor_id": "managerExternalId",
    }

    user = transform_okta_user_to_schema(
        okta_user,
        field_config,
        supervisor_field="timecampSupervisor",
        supervisor_value="yes",
    )

    assert user["email"] == "jane.primary@example.com"
    assert user["department"] == "R&D"
    assert user["job_title"] == "Lead"
    assert user["supervisor_id"] == "mgr-1"
    assert user["is_supervisor"] is True


def test_transform_okta_user_uses_configured_profile_field_as_external_id():
    okta_user = make_okta_user(
        "00u1",
        "jane@example.com",
        manager_id="manager@example.com",
    )

    user = transform_okta_user_to_schema(
        okta_user,
        {
            "external_id": "login",
            "supervisor_id": "managerId",
        },
    )

    assert user["external_id"] == "jane@example.com"
    assert user["supervisor_id"] == "manager@example.com"


def test_resolve_supervisor_id_by_email_to_manager_external_id():
    field_config = {
        "external_id": "employeeNumber",
        "supervisor_id": "managerId",
    }
    employee = transform_okta_user_to_schema(
        make_okta_user(
            "00u-employee",
            "employee@example.com",
            manager_id="MANAGER@example.com",
            extra_profile={"employeeNumber": "employee-100"},
        ),
        field_config,
    )
    manager = transform_okta_user_to_schema(
        make_okta_user(
            "00u-manager",
            "manager@example.com",
            extra_profile={"employeeNumber": "manager-200"},
        ),
        field_config,
    )

    unresolved = resolve_supervisor_ids([employee, manager], field_config, "email")

    assert unresolved == set()
    assert employee["supervisor_id"] == "manager-200"


@patch("fetch_okta.requests.get")
def test_paginated_get_follows_okta_link_header(mock_get):
    mock_get.side_effect = [
        mock_response(
            [make_okta_user("00u1", "one@example.com")],
            links={"next": {"url": "https://example.okta.com/api/v1/users?after=abc&limit=200"}},
        ),
        mock_response([make_okta_user("00u2", "two@example.com")]),
    ]
    client = OktaClient("https://example.okta.com", "token")

    users = list(client.paginated_get("/api/v1/users", params={"limit": 200}))

    assert [user["id"] for user in users] == ["00u1", "00u2"]
    assert mock_get.call_args_list[0].kwargs["params"] == {"limit": 200}
    assert mock_get.call_args_list[1].kwargs["params"] is None


@patch("fetch_okta.requests.get")
def test_find_user_by_id_rejects_a_login_that_does_not_match_the_id(mock_get):
    mock_get.return_value = mock_response(
        make_okta_user("00u-manager", "manager@example.com")
    )
    client = OktaClient("https://example.okta.com", "token")

    user = client.find_user_by_field("id", "manager@example.com")

    assert user is None


@patch("fetch_okta.requests.get")
def test_collect_group_member_ids_uses_exact_group_name(mock_get):
    def side_effect(url, **kwargs):
        if url.endswith("/api/v1/groups"):
            return mock_response([
                {"id": "group-1", "profile": {"name": "Engineering"}},
                {"id": "group-2", "profile": {"name": "Engineering Leads"}},
            ])
        if url.endswith("/api/v1/groups/group-1/users"):
            return mock_response([
                make_okta_user("00u1", "one@example.com"),
                make_okta_user("00u2", "two@example.com"),
            ])
        raise AssertionError(f"Unexpected URL: {url}")

    mock_get.side_effect = side_effect
    client = OktaClient("https://example.okta.com", "token")

    assert collect_group_member_ids(["Engineering"], "filter", client) == {"00u1", "00u2"}


@patch("fetch_okta.requests.get")
def test_collect_group_member_ids_supports_group_ids_and_unions_name_matches(mock_get):
    def side_effect(url, **kwargs):
        if url.endswith("/api/v1/groups"):
            return mock_response([{"id": "00g-name", "profile": {"name": "Engineering"}}])
        if url.endswith("/api/v1/groups/00g-name/users"):
            return mock_response([make_okta_user("00u1", "one@example.com")])
        if url.endswith("/api/v1/groups/00g-direct/users"):
            return mock_response([
                make_okta_user("00u1", "one@example.com"),
                make_okta_user("00u2", "two@example.com"),
            ])
        raise AssertionError(f"Unexpected URL: {url}")

    mock_get.side_effect = side_effect
    client = OktaClient("https://example.okta.com", "token")

    result = collect_group_member_ids(
        ["Engineering"],
        "filter",
        client,
        ["00g-direct"],
    )

    assert result == {"00u1", "00u2"}


@patch("fetch_okta.requests.get")
@patch("common.storage.save_json_file")
def test_fetch_okta_users_fetches_group_members_without_listing_all_users(
    mock_save,
    mock_get,
    mock_env,
    monkeypatch,
):
    monkeypatch.setenv("OKTA_FILTER_GROUP_IDS", "00g-allowed")
    group_users = [
        make_okta_user("00u1", "included@example.com"),
        make_okta_user("00u2", "inactive@example.com", status="SUSPENDED"),
    ]

    def side_effect(url, **kwargs):
        if url.endswith("/api/v1/groups/00g-allowed/users"):
            return mock_response(group_users)
        raise AssertionError(f"Unexpected URL: {url}")

    mock_get.side_effect = side_effect

    fetch_okta_users()

    saved_users = mock_save.call_args[0][0]["users"]
    assert [user["external_id"] for user in saved_users] == ["00u1"]


@patch("fetch_okta.requests.get")
@patch("common.storage.save_json_file")
def test_fetch_okta_users_filters_groups_marks_supervisors_and_fetches_missing_manager(
    mock_save,
    mock_get,
    mock_env,
    monkeypatch,
):
    monkeypatch.setenv("OKTA_FILTER_GROUPS", "TimeCamp Users")
    monkeypatch.setenv("OKTA_SUPERVISOR_GROUPS", "TimeCamp Supervisors")

    manager = make_okta_user("00u-manager", "manager@example.com", display_name="Manager One")

    def side_effect(url, **kwargs):
        params = kwargs.get("params") or {}

        if url.endswith("/api/v1/groups") and params.get("q") == "TimeCamp Users":
            return mock_response([{"id": "group-users", "profile": {"name": "TimeCamp Users"}}])

        if url.endswith("/api/v1/groups") and params.get("q") == "TimeCamp Supervisors":
            return mock_response([{"id": "group-supervisors", "profile": {"name": "TimeCamp Supervisors"}}])

        if url.endswith("/api/v1/groups/group-users/users"):
            return mock_response([
                make_okta_user(
                    "00u1",
                    "user@example.com",
                    display_name="User One",
                    manager_id="00u-manager",
                ),
            ])

        if url.endswith("/api/v1/groups/group-supervisors/users"):
            return mock_response([make_okta_user("00u1", "user@example.com")])

        if url.endswith("/api/v1/users/00u-manager"):
            return mock_response(manager)

        raise AssertionError(f"Unexpected URL: {url}")

    mock_get.side_effect = side_effect

    fetch_okta_users()

    saved_data = mock_save.call_args[0][0]
    users_by_id = {user["external_id"]: user for user in saved_data["users"]}

    assert set(users_by_id) == {"00u1", "00u-manager"}
    assert users_by_id["00u1"]["role_id"] == "2"
    assert users_by_id["00u1"]["supervisor_id"] == "00u-manager"
    assert users_by_id["00u-manager"]["status"] == "inactive"
    assert users_by_id["00u-manager"]["hierarchy_only"] is True
    assert users_by_id["00u-manager"]["raw_data"]["id"] == "00u-manager"


@patch("fetch_okta.requests.get")
@patch("common.storage.save_json_file")
def test_fetch_okta_users_finds_manager_by_email_and_links_external_id(
    mock_save,
    mock_get,
    mock_env,
    monkeypatch,
):
    monkeypatch.setenv("OKTA_EXTERNAL_ID_FIELD", "employeeNumber")
    monkeypatch.setenv("OKTA_SUPERVISOR_MATCH_FIELD", "email")
    employee = make_okta_user(
        "00u-employee",
        "employee@example.com",
        manager_id="manager@example.com",
        extra_profile={"employeeNumber": "employee-100"},
    )
    manager = make_okta_user(
        "00u-manager",
        "manager@example.com",
        extra_profile={"employeeNumber": "manager-200"},
    )

    def side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        if url.endswith("/api/v1/users") and params.get("filter") == 'status eq "ACTIVE"':
            return mock_response([employee])
        if url.endswith("/api/v1/users") and params.get("search") == (
            'profile.email eq "manager@example.com"'
        ):
            return mock_response([manager])
        raise AssertionError(f"Unexpected URL: {url}")

    mock_get.side_effect = side_effect

    fetch_okta_users()

    saved_users = mock_save.call_args[0][0]["users"]
    users_by_id = {user["external_id"]: user for user in saved_users}
    assert set(users_by_id) == {"employee-100", "manager-200"}
    assert users_by_id["employee-100"]["supervisor_id"] == "manager-200"
    assert users_by_id["manager-200"]["status"] == "inactive"
    assert users_by_id["manager-200"]["hierarchy_only"] is True


@patch("fetch_okta.requests.get")
def test_fetch_missing_supervisors_caches_404(mock_get):
    mock_get.return_value = mock_response({"error": "not found"}, status_code=404)
    client = OktaClient("https://example.okta.com", "token")

    result = fetch_missing_supervisors(
        client,
        [{"external_id": "00u1", "supervisor_id": "missing-manager"}],
        {},
    )

    assert result == []
    assert "missing-manager" in fetch_okta.NOT_FOUND_USERS_CACHE


@patch("fetch_okta.requests.get")
@patch("common.storage.save_json_file")
def test_active_user_missing_identity_fields_logs_actionable_okta_validation(
    mock_save,
    mock_get,
    mock_env,
    monkeypatch,
    caplog,
):
    caplog.set_level("INFO")
    monkeypatch.setenv("OKTA_EXTERNAL_ID_FIELD", "employeeNumber")
    monkeypatch.setenv("OKTA_EMAIL_FIELD", "primaryEmail")
    invalid_user = make_okta_user(
        "00u-invalid",
        "login-only@example.com",
        display_name="Example User",
    )
    mock_get.return_value = mock_response([invalid_user])

    with pytest.raises(ValueError, match="Fix the authoritative Okta profile fields"):
        fetch_okta_users()

    mock_save.assert_not_called()
    report = get_logged_okta_validation(caplog)
    assert report["status"] == "failed"
    assert "missing_fields[].okta_field" in report["repair_in_okta"]["missing_identity"]
    assert report["missing_required_fields"] == [{
        "okta_user_id": "00u-invalid",
        "name": "Example User",
        "login": "login-only@example.com",
        "external_id": "",
        "email": "login-only@example.com",
        "missing_fields": [
            {"schema_field": "external_id", "okta_field": "employeeNumber"},
            {"schema_field": "email", "okta_field": "primaryEmail"},
        ],
    }]


@patch("fetch_okta.requests.get")
@patch("common.storage.save_json_file")
def test_duplicate_external_ids_fail_before_replacing_users_artifact(
    mock_save,
    mock_get,
    mock_env,
    monkeypatch,
    caplog,
):
    caplog.set_level("INFO")
    monkeypatch.setenv("OKTA_EXTERNAL_ID_FIELD", "employeeNumber")
    mock_get.return_value = mock_response([
        make_okta_user(
            "00u-one",
            "one@example.com",
            display_name="Example One",
            extra_profile={"employeeNumber": "employee-1"},
        ),
        make_okta_user(
            "00u-two",
            "two@example.com",
            display_name="Example Two",
            extra_profile={"employeeNumber": "employee-1"},
        ),
    ])

    with pytest.raises(ValueError, match="duplicate external ID"):
        fetch_okta_users()

    mock_save.assert_not_called()
    report = get_logged_okta_validation(caplog)
    assert report["duplicate_external_ids"][0]["external_id"] == "employee-1"
    assert {user["okta_user_id"] for user in report["duplicate_external_ids"][0]["users"]} == {
        "00u-one",
        "00u-two",
    }


@patch("fetch_okta.requests.get")
@patch("common.storage.save_json_file")
def test_unresolved_manager_reference_is_reported_and_fails(
    mock_save,
    mock_get,
    mock_env,
    caplog,
):
    caplog.set_level("INFO")
    employee = make_okta_user(
        "00u-employee",
        "employee@example.com",
        display_name="Example Employee",
        manager_id="00u-missing",
    )
    mock_get.side_effect = [
        mock_response([employee]),
        mock_response({"error": "not found"}, status_code=404),
    ]

    with pytest.raises(ValueError, match="unresolved manager reference"):
        fetch_okta_users()

    mock_save.assert_not_called()
    report = get_logged_okta_validation(caplog)
    assert report["unresolved_supervisors"] == [{
        "supervisor_reference": "00u-missing",
        "direct_reports": [{
            "okta_user_id": "00u-employee",
            "name": "Example Employee",
            "login": "employee@example.com",
            "external_id": "00u-employee",
            "email": "employee@example.com",
        }],
    }]


@patch("fetch_okta.requests.get")
@patch("common.storage.save_json_file")
def test_multi_user_manager_cycle_is_reported_and_fails(
    mock_save,
    mock_get,
    mock_env,
    caplog,
):
    caplog.set_level("INFO")
    mock_get.return_value = mock_response([
        make_okta_user("00u-one", "one@example.com", manager_id="00u-two"),
        make_okta_user("00u-two", "two@example.com", manager_id="00u-one"),
    ])

    with pytest.raises(ValueError, match="multi-user manager cycle"):
        fetch_okta_users()

    mock_save.assert_not_called()
    report = get_logged_okta_validation(caplog)
    assert [user["external_id"] for user in report["cycles"][0]] == ["00u-one", "00u-two"]


@patch("fetch_okta.requests.get")
@patch("common.storage.save_json_file")
def test_self_managed_users_are_reported_as_allowed_roots(
    mock_save,
    mock_get,
    mock_env,
    caplog,
):
    caplog.set_level("INFO")
    mock_get.return_value = mock_response([
        make_okta_user("00u-root", "root@example.com", manager_id="00u-root"),
    ])

    fetch_okta_users()

    report = get_logged_okta_validation(caplog)
    saved_users = mock_save.call_args.args[0]["users"]
    assert mock_save.call_count == 1
    assert report["status"] == "passed"
    assert [user["external_id"] for user in report["self_managed_roots"]] == ["00u-root"]
    assert [user["external_id"] for user in report["hierarchy_roots"]] == ["00u-root"]
    assert [user["external_id"] for user in saved_users] == ["00u-root"]


@patch("fetch_okta.requests.get")
@patch("common.storage.save_json_file")
def test_hierarchy_root_limit_is_configurable_and_enforced(
    mock_save,
    mock_get,
    mock_env,
    monkeypatch,
    caplog,
):
    caplog.set_level("INFO")
    monkeypatch.setenv("OKTA_MAX_HIERARCHY_ROOTS", "1")
    mock_get.return_value = mock_response([
        make_okta_user("00u-root-one", "root-one@example.com", manager_id="00u-root-one"),
        make_okta_user("00u-root-two", "root-two@example.com", manager_id="00u-root-two"),
    ])

    with pytest.raises(ValueError, match="hierarchy roots exceeds configured limit 1"):
        fetch_okta_users()

    mock_save.assert_not_called()
    report = get_logged_okta_validation(caplog)
    assert report["root_limit_exceeded"] is True
    assert len(report["hierarchy_roots"]) == 2
