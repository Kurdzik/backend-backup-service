import os
from typing import Optional

import boto3

from src.base import BackupDetails, BaseBackupDestinationManager, Credentials


class S3BackupDestination(BaseBackupDestinationManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.bucket_name, self.prefix = self._parse_s3_url(credentials.url)
        self.s3_client = self._initialize_s3_client()

    def _parse_s3_url(self, url: str) -> tuple[str, str]:
        """Parse S3 compatible URL to extract bucket name and prefix

        Args:
            url: S3 URL in format s3://bucket-name/prefix or s3://bucket-name

        Returns:
            tuple: (bucket_name, prefix)
        """
        if not url.startswith("s3://"):
            raise ValueError("URL must start with s3://")

        # Remove s3:// prefix
        path = url[5:]

        # Split bucket and prefix
        parts = path.split("/", 1)
        bucket_name = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""

        if not bucket_name:
            raise ValueError("Bucket name is required in S3 URL")

        return bucket_name, prefix

    def _initialize_s3_client(self) -> boto3.client:  # ty:ignore[invalid-type-form]
        """Initialize S3 compatible client with provided credentials

        Returns:
            boto3.client: S3 client instance
        """
        session_kwargs = {}
        client_kwargs = {}

        if self.credentials.login and self.credentials.password:
            session_kwargs["aws_access_key_id"] = self.credentials.login
            session_kwargs["aws_secret_access_key"] = self.credentials.password

        # api_key can contain endpoint URL for S3 compatible services
        if self.credentials.api_key:
            client_kwargs["endpoint_url"] = self.credentials.api_key

        session = boto3.Session(**session_kwargs)
        return session.client("s3", **client_kwargs)

    def _get_s3_key(self, filename: str) -> str:
        """Generate S3 object key with prefix

        Args:
            filename: Filename to append to prefix

        Returns:
            str: Full S3 object key
        """
        if self.prefix:
            return f"{self.prefix}/{filename}".lstrip("/")
        return filename

    def upload_backup(self, local_backup_path: str) -> str:
        """Upload backup to S3 compatible bucket

        Args:
            local_backup_path: Path to the local backup file to upload

        Returns:
            str: S3 object key of the uploaded backup
        """
        if not os.path.exists(local_backup_path):
            raise FileNotFoundError(f"Backup file not found: {local_backup_path}")

        filename = os.path.basename(local_backup_path)
        s3_key = self._get_s3_key(filename)

        try:
            self.s3_client.upload_file(local_backup_path, self.bucket_name, s3_key)
            return s3_key
        except Exception as e:
            raise RuntimeError(f"Failed to upload backup to S3: {str(e)}")

    def list_backups(self) -> list[BackupDetails]:
        """List all backups stored in S3 compatible bucket

        Returns:
            list[BackupDetails]: List of backup details
        """
        backups = []

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix)

            for page in pages:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    # Skip if it's the prefix itself or a directory marker
                    if obj["Key"].endswith("/"):
                        continue

                    backup = BackupDetails(
                        name=os.path.basename(obj["Key"]),
                        path=obj["Key"],
                        size=obj["Size"],
                        modified=obj["LastModified"].isoformat(),
                        source=self._parse_filename(os.path.basename(obj["Key"]))[
                            "source"
                        ],
                        source_id=self._parse_filename(os.path.basename(obj["Key"]))[
                            "source_id"
                        ],
                        tenant_id=self._parse_filename(os.path.basename(obj["Key"]))[
                            "tenant_id"
                        ],
                        schedule_id=self._parse_filename(os.path.basename(obj["Key"]))[
                            "schedule_id"
                        ],
                    )
                    backups.append(backup)

            # Sort by modification time (newest first)
            backups.sort(key=lambda x: x.modified, reverse=True)

        except Exception as e:
            raise RuntimeError(f"Failed to list backups from S3: {str(e)}")

        return backups

    def delete_backup(self, backup_path: str) -> None:
        """Delete specified backup from S3 compatible bucket

        Args:
            backup_path: S3 object key of the backup to delete
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=backup_path)
        except Exception as e:
            raise RuntimeError(f"Failed to delete backup from S3: {str(e)}")

    def get_backup(self, backup_path: str, local_path: Optional[str] = None) -> str:
        """Download/retrieve specified backup from S3 compatible bucket

        Args:
            backup_path: S3 object key of the backup to retrieve
            local_path: Optional local path where backup should be saved.
                       If not provided, a random path will be generated.

        Returns:
            str: Path to the downloaded backup file
        """
        if not local_path:
            import uuid

            local_path = str(uuid.uuid4()).replace("-", "")

        try:
            self.s3_client.download_file(self.bucket_name, backup_path, local_path)
            return local_path
        except Exception as e:
            raise RuntimeError(f"Failed to download backup from S3: {str(e)}")

    def _delete_extra_backups(self, keep_n: int = 5) -> None:
        """Delete extra backups from S3 compatible bucket, keeping only the most recent N

        Args:
            keep_n: Number of backups to keep (default: 5)
        """
        backups = self.list_backups()

        # If we have more backups than keep_n, delete the oldest ones
        if len(backups) > keep_n:
            # Backups are already sorted by modification time (newest first)
            # So we delete from index keep_n onwards
            for backup in backups[keep_n:]:
                try:
                    self.delete_backup(backup.path)
                except Exception as e:
                    print(f"Failed to delete backup {backup.path}: {str(e)}")

    def test_connection(self) -> bool:
        """Test whether the S3 compatible bucket is accessible

        Returns:
            bool: True if connection is successful and bucket is accessible, False otherwise
        """
        try:
            # Attempt to list objects in the bucket with a limit of 1
            # This is a lightweight operation to verify connectivity and access
            self.s3_client.list_objects_v2(Bucket=self.bucket_name, MaxKeys=1)
            return True
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False
