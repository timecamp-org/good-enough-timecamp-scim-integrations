from pathlib import Path

from http_service import AVAILABLE_SCRIPTS


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_repo_file(path):
    return (REPO_ROOT / path).read_text()


def test_docker_compose_exposes_hibob_fetcher():
    compose = read_repo_file("docker-compose.yml")

    assert "fetch-hibob:" in compose
    assert 'command: ["python", "fetch_hibob.py"]' in compose

    for variable in (
        "HIBOB_SERVICE_USER_ID",
        "HIBOB_SERVICE_USER_TOKEN",
        "HIBOB_EXCLUDE_FILTER",
        "HIBOB_EXCLUDED_DEPARTMENTS",
        "HIBOB_SUPERVISOR_RULE",
        "HIBOB_CUSTOM_FIELDS",
    ):
        assert f"- {variable}=" in compose


def test_http_service_allows_hibob_fetcher():
    assert "fetch_hibob.py" in AVAILABLE_SCRIPTS


def test_helm_chart_exposes_hibob_fetcher():
    values = read_repo_file("helm/timecamp-scim/values.yaml")
    helpers = read_repo_file("helm/timecamp-scim/templates/_helpers.tpl")
    cronjob = read_repo_file("helm/timecamp-scim/templates/cronjob-fetch-hibob.yaml")

    assert "fetchHibob:" in values
    assert 'command: ["python", "fetch_hibob.py"]' in values
    assert "hibob:" in values
    assert "serviceUserId:" in values
    assert "customFields:" in values

    assert "HIBOB_SERVICE_USER_ID" in helpers
    assert "HIBOB_SERVICE_USER_TOKEN" in helpers
    assert "HIBOB_EXCLUDE_FILTER" in helpers
    assert ".Values.jobs.fetchHibob.enabled" in helpers

    assert "{{- if .Values.jobs.fetchHibob.enabled }}" in cronjob
    assert "timecamp-scim-fetch-hibob" in cronjob
    assert "app.kubernetes.io/component: fetch-hibob" in cronjob
    assert ".Values.jobs.fetchHibob.command" in cronjob


def test_hibob_secret_is_documented_for_kubernetes():
    external_secret = read_repo_file("helm/timecamp-scim/templates/externalsecrets.yaml")
    sample_secret = read_repo_file("helm/timecamp-scim/samples/secrets/scim-secrets.json")
    google_secret_docs = read_repo_file("docs/kubernetes/secret-stores/google-secret-manager.md")

    assert "HIBOB_SERVICE_USER_TOKEN" in external_secret
    assert ".Values.jobs.fetchHibob.enabled" in external_secret
    assert "HIBOB_SERVICE_USER_TOKEN" in sample_secret
    assert "HIBOB_SERVICE_USER_TOKEN" in google_secret_docs


def test_hibob_docs_cover_local_docker_and_kubernetes_usage():
    readme = read_repo_file("README.md")
    docker_docs = read_repo_file("docs/docker.md")
    hibob_docs = read_repo_file("docs/fetch_hibob.md")
    helm_docs = read_repo_file("docs/kubernetes/deployment/02-helm-installation.md")

    assert "docs/fetch_hibob.md" in readme
    assert "fetch-hibob" in docker_docs
    assert "fetch_hibob.py" in docker_docs

    assert "HIBOB_SERVICE_USER_ID" in hibob_docs
    assert "HIBOB_SERVICE_USER_TOKEN" in hibob_docs
    assert "HIBOB_EXCLUDED_DEPARTMENTS" in hibob_docs

    assert "fetchHibob:" in helm_docs
    assert "HIBOB_SERVICE_USER_TOKEN" in helm_docs
