from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_http_script_runner_is_not_shipped():
    compose = (REPO_ROOT / "docker-compose.yml").read_text()

    assert "http-service:" not in compose
    assert "8181:8181" not in compose
    assert not (REPO_ROOT / "http_service.py").exists()
