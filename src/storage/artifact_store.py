from __future__ import annotations
import json
from pathlib import Path
from typing import Protocol


class ArtifactStore(Protocol):
    def write_json(self, key: str, data: dict) -> str: ...
    def write_bytes(self, key: str, data: bytes) -> str: ...
    def read_json(self, key: str) -> dict: ...
    def path_for(self, key: str) -> str: ...


class LocalArtifactStore:
    """Filesystem-backed store using S3-key-shaped relative paths under base_dir."""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

    def _full_path(self, key: str) -> Path:
        full = self.base_dir / key
        full.parent.mkdir(parents=True, exist_ok=True)
        return full

    def write_json(self, key: str, data: dict) -> str:
        full = self._full_path(key)
        full.write_text(json.dumps(data, indent=2))
        return str(full)

    def write_bytes(self, key: str, data: bytes) -> str:
        full = self._full_path(key)
        full.write_bytes(data)
        return str(full)

    def read_json(self, key: str) -> dict:
        return json.loads((self.base_dir / key).read_text())

    def path_for(self, key: str) -> str:
        return str(self.base_dir / key)


class S3ArtifactStore:
    """boto3 S3-backed store, same key shape as LocalArtifactStore."""

    def __init__(self, bucket: str, s3_client):
        self.bucket = bucket
        self.s3 = s3_client

    def write_json(self, key: str, data: dict) -> str:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=json.dumps(data, indent=2).encode())
        return f"s3://{self.bucket}/{key}"

    def write_bytes(self, key: str, data: bytes) -> str:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)
        return f"s3://{self.bucket}/{key}"

    def read_json(self, key: str) -> dict:
        obj = self.s3.get_object(Bucket=self.bucket, Key=key)
        return json.loads(obj["Body"].read())

    def path_for(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"
