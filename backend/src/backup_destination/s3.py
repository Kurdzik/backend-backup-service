import os
import uuid
from datetime import datetime
from typing import Optional

import boto3
import botocore.exceptions
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
            raise FileNotFoundError(f"Backup file not found: {local_backup_path}")

        filename = os.path.basename(local_backup_path)
        key = self._key(filename)

        file_exists = False
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            file_exists = True
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] != '404':
                raise RuntimeError(f"Failed to check S3 for existing file: {e}") from e

        if file_exists:
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}{ext}"
            key = self._key(filename)

        try:
            self.s3_client.upload_file(
                local_backup_path,
                self.bucket_name,
                key
            )
            return key
        except Exception as e:
            raise RuntimeError(f"S3 upload failed: {e}") from e

    def list_backups(self) -> list[BackupDetails]:
        backups: list[BackupDetails] = []

        paginator = self.s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(
            Bucket=self.bucket_name,
            Prefix=f"{self.prefix}/" if self.prefix else "",
        )

        for page in pages:
            for obj in page.get("Contents", []):
                if obj["Key"].endswith("/"):
                    continue

                name = os.path.basename(obj["Key"])
                meta = self._parse_filename(name)

                backup = BackupDetails(
                    name=name,
                    path=obj["Key"],
                    size=obj["Size"],
                    modified=obj["LastModified"].isoformat(),
                    source=meta["source"],
                    tenant_id=meta["tenant_id"],
                    schedule_id=meta["schedule_id"],
                    source_id=meta["source_id"],
                )
                backups.append(backup)

        backups.sort(key=lambda x: x.modified, reverse=True)

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
            local_path = str(uuid.uuid4()).replace("-", "")

        try:
            self.s3_client.download_file(
                self.bucket_name,
                backup_path,
                local_path,
            )
            return local_path
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise FileNotFoundError(f"Backup file not found in S3: {backup_path}")
            raise RuntimeError(f"S3 download failed: {e}") from e

    def _delete_extra_backups(self, keep_n: int = 5) -> None:
        backups = self.list_backups()

        if len(backups) > keep_n:
            for backup in backups[keep_n:]:
                try:
                    self.delete_backup(backup.path)
                except Exception as e:
                    print(f"Failed to delete backup {backup.path}: {str(e)}")

    def test_connection(self) -> bool:
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except Exception as e:
            print(f"S3 Connection test failed: {str(e)}")
            return False