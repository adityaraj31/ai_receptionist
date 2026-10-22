from __future__ import annotations

from app.services import storage


def test_storage_accepts_iam_role_when_keys_are_absent(monkeypatch):
    monkeypatch.setattr(storage.settings, "s3_bucket", "recordings")
    monkeypatch.setattr(storage.settings, "s3_access_key_id", "")
    monkeypatch.setattr(storage.settings, "s3_secret_access_key", "")

    assert storage._configured() is True


def test_storage_rejects_partial_static_credentials(monkeypatch):
    monkeypatch.setattr(storage.settings, "s3_bucket", "recordings")
    monkeypatch.setattr(storage.settings, "s3_access_key_id", "key")
    monkeypatch.setattr(storage.settings, "s3_secret_access_key", "")

    assert storage._configured() is False


def test_storage_client_uses_default_chain_without_static_keys(monkeypatch):
    captured: dict = {}

    class FakeBoto3:
        def client(self, service: str, **kwargs):
            captured["service"] = service
            captured.update(kwargs)
            return object()

    monkeypatch.setattr(storage, "boto3", FakeBoto3())
    monkeypatch.setattr(storage.settings, "s3_endpoint_url", "")
    monkeypatch.setattr(storage.settings, "s3_region", "ap-south-1")
    monkeypatch.setattr(storage.settings, "s3_access_key_id", "")
    monkeypatch.setattr(storage.settings, "s3_secret_access_key", "")

    storage._client()

    assert captured["service"] == "s3"
    assert "aws_access_key_id" not in captured
    assert "aws_secret_access_key" not in captured
