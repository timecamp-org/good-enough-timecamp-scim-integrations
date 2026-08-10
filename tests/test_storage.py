import hashlib
import io
import json
import logging
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from common.storage import StorageService


def make_s3_storage():
    storage = StorageService.__new__(StorageService)
    storage.use_s3 = True
    storage.s3_bucket_name = "example-artifacts"
    storage.s3_path_prefix = "integration"
    storage.s3_client = Mock()
    storage.ClientError = type("ClientError", (Exception,), {})
    return storage


def test_local_artifact_save_and_load_logs_digest_and_timestamp(tmp_path, caplog, monkeypatch):
    monkeypatch.setenv("USE_S3_STORAGE", "false")
    storage = StorageService()
    artifact_path = tmp_path / "users.json"
    data = {"users": [{"external_id": "employee-1"}]}
    expected_content = json.dumps(data, indent=2, ensure_ascii=False).encode()
    expected_digest = hashlib.sha256(expected_content).hexdigest()

    with caplog.at_level(logging.INFO, logger="storage"):
        storage.save_json(data, str(artifact_path))
        loaded = storage.load_json(str(artifact_path))

    assert loaded == data
    assert f"sha256={expected_digest}" in caplog.text
    assert "Artifact saved: storage=local" in caplog.text
    assert "Artifact loaded: storage=local" in caplog.text
    assert "artifact_timestamp=" in caplog.text


def test_s3_artifact_has_integrity_metadata():
    storage = make_s3_storage()
    data = {"users": []}
    expected_content = json.dumps(data, indent=2, ensure_ascii=False).encode()
    expected_digest = hashlib.sha256(expected_content).hexdigest()

    storage.save_json(data, "var/users.json")

    request = storage.s3_client.put_object.call_args.kwargs
    assert request["Bucket"] == "example-artifacts"
    assert request["Key"] == "integration/var/users.json"
    assert request["Body"] == expected_content
    assert request["Metadata"]["sha256"] == expected_digest
    assert request["Metadata"]["generated-at"]


def test_s3_artifact_digest_is_verified_on_load():
    storage = make_s3_storage()
    content = json.dumps({"users": []}).encode()
    digest = hashlib.sha256(content).hexdigest()
    storage.s3_client.get_object.return_value = {
        "Body": io.BytesIO(content),
        "Metadata": {"sha256": digest},
        "LastModified": datetime(2026, 8, 10, tzinfo=timezone.utc),
    }

    assert storage.load_json("var/users.json") == {"users": []}


def test_s3_artifact_digest_mismatch_fails_closed():
    storage = make_s3_storage()
    storage.s3_client.get_object.return_value = {
        "Body": io.BytesIO(b'{"users": []}'),
        "Metadata": {"sha256": "0" * 64},
        "LastModified": datetime(2026, 8, 10, tzinfo=timezone.utc),
    }

    with pytest.raises(ValueError, match="Artifact integrity check failed"):
        storage.load_json("var/users.json")
