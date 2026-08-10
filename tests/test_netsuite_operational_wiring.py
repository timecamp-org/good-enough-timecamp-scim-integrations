from pathlib import Path

from http_service import AVAILABLE_SCRIPTS

REPO_ROOT = Path(__file__).resolve().parents[1]


def read_repo_file(path):
    return (REPO_ROOT / path).read_text()


def test_docker_and_http_expose_netsuite_fetcher():
    compose = read_repo_file("docker-compose.yml")

    assert "fetch-netsuite:" in compose
    assert 'command: ["python", "fetch_netsuite.py"]' in compose
    assert "fetch_netsuite.py" in AVAILABLE_SCRIPTS

    for variable in (
        "NETSUITE_ACCOUNT_ID",
        "NETSUITE_CLIENT_ID",
        "NETSUITE_CERTIFICATE_ID",
        "NETSUITE_PRIVATE_KEY",
        "NETSUITE_PRIVATE_KEY_PATH",
        "NETSUITE_BASE_URL",
        "NETSUITE_EMPLOYEE_QUERY",
        "NETSUITE_GROUP_QUERY",
        "NETSUITE_PAGE_SIZE",
        "NETSUITE_TIMEOUT_SECONDS",
        "NETSUITE_SSL_VERIFY",
        "NETSUITE_ALLOW_EMPTY_RESULT",
        "NETSUITE_JWT_ALGORITHM",
    ):
        assert f"- {variable}=" in compose


def test_helm_chart_exposes_netsuite_fetcher_and_configuration():
    values = read_repo_file("helm/timecamp-scim/values.yaml")
    helpers = read_repo_file("helm/timecamp-scim/templates/_helpers.tpl")
    cronjob = read_repo_file("helm/timecamp-scim/templates/cronjob-fetch-netsuite.yaml")
    external_secret = read_repo_file(
        "helm/timecamp-scim/templates/externalsecrets.yaml"
    )

    assert "fetchNetsuite:" in values
    assert 'command: ["python", "fetch_netsuite.py"]' in values
    assert "netsuite:" in values
    for field in (
        "accountId:",
        "clientId:",
        "certificateId:",
        "privateKeyPath:",
        "employeeQuery:",
        "groupQuery:",
        "pageSize:",
        "timeoutSeconds:",
        "sslVerify:",
        "allowEmptyResult:",
        "jwtAlgorithm:",
    ):
        assert field in values

    for variable in (
        "NETSUITE_ACCOUNT_ID",
        "NETSUITE_CLIENT_ID",
        "NETSUITE_CERTIFICATE_ID",
        "NETSUITE_PRIVATE_KEY",
        "NETSUITE_EMPLOYEE_QUERY",
        "NETSUITE_GROUP_QUERY",
        "NETSUITE_ALLOW_EMPTY_RESULT",
    ):
        assert variable in helpers

    assert "{{- if .Values.jobs.fetchNetsuite.enabled }}" in cronjob
    assert "timecamp-scim-fetch-netsuite" in cronjob
    assert ".Values.jobs.fetchNetsuite.command" in cronjob
    assert "NETSUITE_PRIVATE_KEY" in external_secret


def test_netsuite_configuration_and_runbook_are_documented():
    readme = read_repo_file("README.md")
    env_example = read_repo_file("docs/.env.example")
    docs = read_repo_file("docs/fetch_netsuite.md")
    docker_docs = read_repo_file("docs/docker.md")
    kubernetes_docs = read_repo_file(
        "docs/kubernetes/deployment/02-helm-installation.md"
    )
    sample_secret = read_repo_file(
        "helm/timecamp-scim/samples/secrets/scim-secrets.json"
    )

    assert "docs/fetch_netsuite.md" in readme
    assert "NETSUITE_ACCOUNT_ID" in env_example
    assert "OAuth 2.0 client credentials" in docs
    assert "NETSUITE_ALLOW_EMPTY_RESULT" in docs
    assert "fetch-netsuite" in docker_docs
    assert "fetchNetsuite:" in kubernetes_docs
    assert "NETSUITE_PRIVATE_KEY" in sample_secret
