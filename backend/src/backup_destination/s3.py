import os
import uuid
from typing import Optional

import boto3
from botocore.config import Config

from src.base import BackupDetails, BaseBackupDestinationManager, Credentials


class S3BackupDestination(BaseBackupDestinationManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.bucket_name, self.prefix = self._parse_s3_url(credentials.url)
        self.s3_client = self._initialize_s3_client()

    def _parse_s3_url(self, url: str) -> tuple[str, str]:
        if not url.startswith("s3://"):
            raise ValueError("URL must start with s3://")

        path = url[5:]
        parts = path.split("/", 1)
        bucket = parts[0]
        prefix = parts[1].rstrip("/") if len(parts) > 1 else ""

        if not bucket:
            raise ValueError("Bucket name is required")

        return bucket, prefix

    def _initialize_s3_client(self):
        session_kwargs = {}
        client_kwargs = {}

        if self.credentials.login and self.credentials.password:
            session_kwargs["aws_access_key_id"] = self.credentials.login
            session_kwargs["aws_secret_access_key"] = self.credentials.password

        if self.credentials.api_key:
            client_kwargs["endpoint_url"] = self.credentials.api_key

        # Safe defaults for S3-compatible storage
        client_kwargs["config"] = Config(
            signature_version="s3v4",
            retries={"max_attempts": 5},
        )

        session = boto3.Session(**session_kwargs)
        return session.client("s3", **client_kwargs)

    def _key(self, filename: str) -> str:
        return f"{self.prefix}/{filename}" if self.prefix else filename

    def upload_backup(self, local_backup_path: str) -> str:
        if not os.path.exists(local_backup_path):
            raise FileNotFoundError(local_backup_path)

        filename = os.path.basename(local_backup_path)

        # Always make key unique (filesystem semantics emulation)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        key = self._key(unique_name)

        try:
            self.s3_client.upload_file(
                local_backup_path,
                self.bucket_name,
                key,
                ExtraArgs={"ACL": "private"},
            )
            return key
        except Exception as e:
            raise RuntimeError(f"S3 upload failed: {e}") from e

    def list_backups(self) -> list[BackupDetails]:
        backups: list[BackupDetails] = []

        paginator = self.s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(
            Bucket=self.bucket_name,
            Prefix=f"{self.prefix}/" if self.prefix else None,
        )

        for page in pages:
            for obj in page.get("Contents", []):
                if obj["Key"].endswith("/"):
                    continue

                name = os.path.basename(obj["Key"])
                meta = self._parse_filename(name)

                backups.append(
                    BackupDetails(
                        name=name,
                        path=obj["Key"],
                        size=obj["Size"],
                        modified=obj["LastModified"].isoformat(),
                        source=meta["source"],
                        tenant_id=meta["tenant_id"],
                        schedule_id=meta["schedule_id"],
                        source_id=meta["source_id"],
                    )
                )

        backups.sort(key=lambda b: b.modified, reverse=True)
        return backups

    def delete_backup(self, backup_path: str) -> None:
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=backup_path,
            )
        except Exception as e:
            raise RuntimeError(f"S3 delete failed: {e}") from e

    def get_backup(self, backup_path: str, local_path: Optional[str] = None) -> str:
        if not local_path:
            local_path = os.path.join(
                "/tmp", f"s3_restore_{uuid.uuid4().hex}"
            )

        try:
            self.s3_client.download_file(
                self.bucket_name,
                backup_path,
                local_path,
            )
            return local_path
        except Exception as e:
            raise RuntimeError(f"S3 download failed: {e}") from e

    def test_connection(self) -> bool:
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except Exception:
            return False
