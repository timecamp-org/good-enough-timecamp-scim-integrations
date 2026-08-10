from unittest.mock import Mock, call, patch

import pytest

from fetch_netsuite import (
    DEFAULT_EMPLOYEE_QUERY,
    DEFAULT_GROUP_QUERY,
    NetSuiteClient,
    NetSuiteConfig,
    build_group_paths,
    fetch_netsuite_users,
    transform_employees,
)
from prepare_timecamp_json_from_fetch import prepare_timecamp_users


def make_config(**overrides):
    values = {
        "account_id": "123456_SB1",
        "client_id": "client-id",
        "certificate_id": "certificate-id",
        "private_key": "private-key",
        "employee_query": DEFAULT_EMPLOYEE_QUERY,
        "group_query": DEFAULT_GROUP_QUERY,
        "page_size": 2,
        "timeout_seconds": 15,
        "ssl_verify": True,
    }
    values.update(overrides)
    return NetSuiteConfig(**values)


def response(json_data, status_code=200, headers=None):
    result = Mock()
    result.status_code = status_code
    result.headers = headers or {}
    result.json.return_value = json_data
    result.raise_for_status.return_value = None
    return result


def test_config_reads_oauth2_credentials_and_normalizes_sandbox_domain(monkeypatch):
    monkeypatch.setenv("NETSUITE_ACCOUNT_ID", "123456_SB1")
    monkeypatch.setenv("NETSUITE_CLIENT_ID", "client-id")
    monkeypatch.setenv("NETSUITE_CERTIFICATE_ID", "certificate-id")
    monkeypatch.setenv(
        "NETSUITE_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\\nkey\\n-----END PRIVATE KEY-----",
    )
    monkeypatch.setenv("NETSUITE_PAGE_SIZE", "500")
    monkeypatch.setenv("NETSUITE_EMPLOYEE_QUERY", "")
    monkeypatch.setenv("NETSUITE_GROUP_QUERY", "")

    config = NetSuiteConfig.from_env()

    assert config.service_url == "https://123456-sb1.suitetalk.api.netsuite.com"
    assert "\nkey\n" in config.private_key
    assert config.page_size == 500
    assert config.jwt_algorithm == "PS256"
    assert config.employee_query == DEFAULT_EMPLOYEE_QUERY
    assert config.group_query == DEFAULT_GROUP_QUERY


def test_config_rejects_page_size_above_netsuite_limit(monkeypatch):
    monkeypatch.setenv("NETSUITE_ACCOUNT_ID", "123456")
    monkeypatch.setenv("NETSUITE_CLIENT_ID", "client-id")
    monkeypatch.setenv("NETSUITE_CERTIFICATE_ID", "certificate-id")
    monkeypatch.setenv("NETSUITE_PRIVATE_KEY", "private-key")
    monkeypatch.setenv("NETSUITE_PAGE_SIZE", "1001")

    with pytest.raises(ValueError, match="NETSUITE_PAGE_SIZE must not exceed 1000"):
        NetSuiteConfig.from_env()


def test_client_requests_and_caches_oauth2_access_token():
    session = Mock()
    session.post.return_value = response(
        {"access_token": "access-token", "expires_in": 3600}
    )
    client = NetSuiteClient(make_config(), session=session, now=lambda: 1000)

    with patch("fetch_netsuite.jwt.encode", return_value="signed-assertion") as encode:
        first = client._get_access_token()
        second = client._get_access_token()

    assert first == second == "access-token"
    assert session.post.call_count == 1
    payload = encode.call_args.args[0]
    headers = encode.call_args.kwargs["headers"]
    assert payload["iss"] == "client-id"
    assert payload["scope"] == ["rest_webservices"]
    assert payload["aud"] == client.token_url
    assert payload["exp"] == 1300
    assert headers["kid"] == "certificate-id"
    assert (
        session.post.call_args.kwargs["data"]["client_assertion"] == "signed-assertion"
    )


def test_suiteql_paginates_using_returned_count():
    client = NetSuiteClient(make_config())
    client._post_suiteql_page = Mock(
        side_effect=[
            {"count": 2, "hasMore": True, "items": [{"id": "1"}, {"id": "2"}]},
            {"count": 1, "hasMore": False, "items": [{"id": "3"}]},
        ]
    )

    rows = client.run_suiteql("SELECT id FROM employee")

    assert rows == [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    assert client._post_suiteql_page.call_args_list == [
        call("SELECT id FROM employee", 0),
        call("SELECT id FROM employee", 2),
    ]


def test_suiteql_retries_rate_limit_using_retry_after():
    session = Mock()
    session.post.side_effect = [
        response({}, status_code=429, headers={"Retry-After": "3"}),
        response({"count": 1, "hasMore": False, "items": [{"id": "1"}]}),
    ]
    sleep = Mock()
    client = NetSuiteClient(make_config(), session=session, sleep=sleep)
    client._get_access_token = Mock(return_value="access-token")

    page = client._post_suiteql_page("SELECT id FROM employee", 0)

    assert page["items"] == [{"id": "1"}]
    assert session.post.call_count == 2
    sleep.assert_called_once_with(3.0)


def test_build_group_paths_handles_multiple_levels_and_case_insensitive_aliases():
    paths = build_group_paths(
        [
            {"GROUP_ID": "10", "GROUP_NAME": "Operations", "PARENT_ID": None},
            {"group_id": "20", "group_name": "Delivery", "parent_id": "10"},
            {"group_id": "30", "group_name": "Quality", "parent_id": "20"},
        ]
    )

    assert paths == {
        "10": "Operations",
        "20": "Operations/Delivery",
        "30": "Operations/Delivery/Quality",
    }


def test_build_group_paths_rejects_cycles():
    with pytest.raises(ValueError, match="Cycle in NetSuite group hierarchy"):
        build_group_paths(
            [
                {"group_id": "10", "group_name": "One", "parent_id": "20"},
                {"group_id": "20", "group_name": "Two", "parent_id": "10"},
            ]
        )


def test_transform_employees_maps_groups_status_and_supervisor_role():
    users = transform_employees(
        [
            {
                "EXTERNAL_ID": 100,
                "EMAIL": "manager@example.com",
                "FIRST_NAME": "Generic",
                "LAST_NAME": "Manager",
                "GROUP_ID": 20,
                "STATUS": "active",
            },
            {
                "external_id": 101,
                "email": "person@example.com",
                "name": "Generic Person",
                "group_id": 20,
                "supervisor_id": 100,
                "status": "inactive",
                "job_title": "Specialist",
            },
        ],
        {"20": "Operations/Delivery"},
    )

    assert users[0]["name"] == "Generic Manager"
    assert users[0]["department"] == "Operations/Delivery"
    assert users[0]["is_supervisor"] is True
    assert users[1]["status"] == "inactive"
    assert users[1]["supervisor_id"] == "100"


def test_netsuite_users_feed_existing_timecamp_group_pipeline(mock_timecamp_config):
    users = transform_employees(
        [
            {
                "external_id": "100",
                "email": "person@example.com",
                "name": "Generic Person",
                "group_id": "20",
                "status": "active",
            }
        ],
        {"20": "Operations/Delivery"},
    )

    prepared = prepare_timecamp_users({"users": users}, mock_timecamp_config)

    assert prepared[0]["timecamp_email"] == "person@example.com"
    assert prepared[0]["timecamp_groups_breadcrumb"] == "Operations/Delivery"


def test_fetch_netsuite_users_saves_existing_pipeline_contract():
    config = make_config()
    client = Mock()
    client.run_suiteql.side_effect = [
        [{"group_id": "10", "group_name": "Operations", "parent_id": None}],
        [
            {
                "external_id": "100",
                "email": "person@example.com",
                "name": "Generic Person",
                "group_id": "10",
                "status": "active",
            }
        ],
    ]

    with patch("fetch_netsuite.save_json_file") as save:
        result = fetch_netsuite_users(config=config, client=client)

    assert result["users"][0]["department"] == "Operations"
    assert client.run_suiteql.call_args_list == [
        call(DEFAULT_GROUP_QUERY),
        call(DEFAULT_EMPLOYEE_QUERY),
    ]
    save.assert_called_once_with(result, "var/users.json")


def test_fetch_netsuite_users_does_not_overwrite_source_on_empty_active_result():
    config = make_config()
    client = Mock()
    client.run_suiteql.side_effect = [[], []]

    with (
        patch("fetch_netsuite.save_json_file") as save,
        pytest.raises(ValueError, match="refusing to overwrite"),
    ):
        fetch_netsuite_users(config=config, client=client)

    save.assert_not_called()


def test_fetch_netsuite_users_allows_deliberate_empty_result():
    config = make_config(allow_empty_result=True)
    client = Mock()
    client.run_suiteql.side_effect = [[], []]

    with patch("fetch_netsuite.save_json_file") as save:
        result = fetch_netsuite_users(config=config, client=client)

    assert result == {"users": []}
    save.assert_called_once_with(result, "var/users.json")
