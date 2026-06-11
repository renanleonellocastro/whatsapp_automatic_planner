"""Unit tests for the S3 storage adapter (FR-ING-07, FR-RND-03)."""

from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import ClientError

from wapp_planner.providers.s3_storage import S3Storage


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeS3:
    def __init__(self) -> None:
        self.store: dict[str, tuple[bytes, str]] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:  # noqa: N803
        self.store[Key] = (Body, ContentType)

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        if Key not in self.store:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": _Body(self.store[Key][0])}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        if Key not in self.store:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}

    def delete_object(self, *, Bucket: str, Key: str) -> None:  # noqa: N803
        self.store.pop(Key, None)


def _storage() -> tuple[S3Storage, _FakeS3]:
    client = _FakeS3()
    return S3Storage(client, "my-bucket"), client


def test_put_returns_s3_uri_and_stores() -> None:
    storage, client = _storage()
    ref = storage.put("k1", b"data", content_type="text/plain")
    assert ref == "s3://my-bucket/k1"
    assert client.store["k1"] == (b"data", "text/plain")


def test_get_returns_bytes() -> None:
    storage, _ = _storage()
    storage.put("k1", b"data", content_type="text/plain")
    assert storage.get("k1") == b"data"


def test_get_missing_raises() -> None:
    storage, _ = _storage()
    with pytest.raises(ClientError):
        storage.get("missing")


def test_exists_true_and_false() -> None:
    storage, _ = _storage()
    assert not storage.exists("k1")
    storage.put("k1", b"x", content_type="text/plain")
    assert storage.exists("k1")


def test_delete() -> None:
    storage, _ = _storage()
    storage.put("k1", b"x", content_type="text/plain")
    storage.delete("k1")
    assert not storage.exists("k1")
