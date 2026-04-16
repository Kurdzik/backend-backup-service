import os
import tarfile
import tempfile
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import boto3
from botocore.client import Config

from src.base import BaseBackupManager, Credentials


class MinIOBackupManager(BaseBackupManager):
    """Backs up all objects from all MinIO buckets into a single tar.gz archive.

    Credentials mapping:
      url      — MinIO endpoint, e.g. http://minio.example.com:9000
      login    — Access key ID
      password — Secret access key
    """

    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.client = self._initialize_client()

    def _initialize_client(self):
        parsed = urlparse(self.credentials.url)
        use_ssl = parsed.scheme == "https"

        return boto3.client(
            "s3",
            endpoint_url=self.credentials.url,
            aws_access_key_id=self.credentials.login,
            aws_secret_access_key=self.credentials.password,
            config=Config(signature_version="s3v4"),
            use_ssl=use_ssl,
        )

    def create_backup(
        self, tenant_id: str, backup_source_id: int, schedule_id: Optional[int] = None
    ) -> str:
        temp_dir = tempfile.mkdtemp()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"minio_backup_usr={tenant_id}_sch={schedule_id}_src={backup_source_id}_created_at={timestamp}.tar.gz"

        try:
            buckets = self.client.list_buckets().get("Buckets", [])

            for bucket in buckets:
                bucket_name = bucket["Name"]
                bucket_dir = os.path.join(temp_dir, bucket_name)
                os.makedirs(bucket_dir, exist_ok=True)

                paginator = self.client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket_name):
                    for obj in page.get("Contents", []):
                        key = obj["Key"]
                        local_file = os.path.join(bucket_dir, key)
                        os.makedirs(os.path.dirname(local_file), exist_ok=True)
                        self.client.download_file(bucket_name, key, local_file)

            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(temp_dir, arcname="minio_backup")

            return backup_path

        finally:
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir_name in dirs:
                    os.rmdir(os.path.join(root, dir_name))
            os.rmdir(temp_dir)

    def restore_from_backup(self, backup_path: str) -> None:
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        temp_dir = tempfile.mkdtemp()

        try:
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(temp_dir)

            backup_root = os.path.join(temp_dir, "minio_backup")

            for bucket_name in os.listdir(backup_root):
                bucket_path = os.path.join(backup_root, bucket_name)
                if not os.path.isdir(bucket_path):
                    continue

                try:
                    self.client.create_bucket(Bucket=bucket_name)
                except self.client.exceptions.BucketAlreadyOwnedByYou:
                    pass
                except Exception:
                    pass

                for dirpath, _, filenames in os.walk(bucket_path):
                    for filename in filenames:
                        local_file = os.path.join(dirpath, filename)
                        key = os.path.relpath(local_file, bucket_path)
                        self.client.upload_file(local_file, bucket_name, key)

        finally:
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir_name in dirs:
                    os.rmdir(os.path.join(root, dir_name))
            os.rmdir(temp_dir)

    def test_connection(self) -> bool:
        try:
            self.client.list_buckets()
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
