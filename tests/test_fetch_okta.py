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
    monkeypatch.setenv("OKTA_SUPERVISOR_GROUPS", "")
    monkeypatch.setenv("OKTA_EXCLUDED_DEPARTMENTS", "")
    monkeypatch.setenv("OKTA_EMAIL_FIELD", "email")
    monkeypatch.setenv("OKTA_NAME_FIELD", "displayName")
    monkeypatch.setenv("OKTA_DEPARTMENT_FIELD", "department")
    monkeypatch.setenv("OKTA_JOB_TITLE_FIELD", "title")
    monkeypatch.setenv("OKTA_SUPERVISOR_ID_FIELD", "managerId")
    monkeypatch.setenv("OKTA_SUPERVISOR_RULE", "")


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
@patch("common.storage.save_json_file")
def test_fetch_okta_users_filters_groups_marks_supervisors_and_fetches_missing_manager(
    mock_save,
    mock_get,
    mock_env,
    monkeypatch,
):
    monkeypatch.setenv("OKTA_FILTER_GROUPS", "TimeCamp Users")
    monkeypatch.setenv("OKTA_SUPERVISOR_GROUPS", "TimeCamp Supervisors")

    active_users = [
        make_okta_user("00u1", "user@example.com", display_name="User One", manager_id="00u-manager"),
        make_okta_user("00u2", "outsider@example.com", display_name="Out Sider"),
    ]
    manager = make_okta_user("00u-manager", "manager@example.com", display_name="Manager One")

    def side_effect(url, **kwargs):
        params = kwargs.get("params") or {}

        if url.endswith("/api/v1/groups") and params.get("q") == "TimeCamp Users":
            return mock_response([{"id": "group-users", "profile": {"name": "TimeCamp Users"}}])

        if url.endswith("/api/v1/groups") and params.get("q") == "TimeCamp Supervisors":
            return mock_response([{"id": "group-supervisors", "profile": {"name": "TimeCamp Supervisors"}}])

        if url.endswith("/api/v1/groups/group-users/users"):
            return mock_response([
                make_okta_user("00u1", "user@example.com"),
                make_okta_user("00u-manager", "manager@example.com"),
            ])

        if url.endswith("/api/v1/groups/group-supervisors/users"):
            return mock_response([make_okta_user("00u1", "user@example.com")])

        if url.endswith("/api/v1/users") and params.get("filter") == 'status eq "ACTIVE"':
            return mock_response(active_users)

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
    assert users_by_id["00u-manager"]["raw_data"]["id"] == "00u-manager"


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
