"""S3-backed object storage adapter (FR-ING-07, FR-RND-03).

Wraps an injected boto3 S3 client so it is unit-tested with a fake client of the
same shape. References are ``s3://<bucket>/<key>``.
"""

from __future__ import annotations

from typing import Any, Protocol

from botocore.exceptions import ClientError

from wapp_planner.providers.base import StorageProvider


class _S3Client(Protocol):  # pragma: no cover - structural typing only
    def put_object(self, **kwargs: Any) -> Any: ...
    def get_object(self, **kwargs: Any) -> Any: ...
    def head_object(self, **kwargs: Any) -> Any: ...
    def delete_object(self, **kwargs: Any) -> Any: ...


class S3Storage(StorageProvider):
    """Object storage on an S3 bucket."""

    def __init__(self, client: _S3Client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put(self, key: str, data: bytes, *, content_type: str) -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{self._bucket}/{key}"

    def get(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        body: bytes = response["Body"].read()
        return body

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError:
            return False
        return True

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)
