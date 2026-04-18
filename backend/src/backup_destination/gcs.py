import json
import os
import uuid
from typing import Optional

from google.cloud import storage
from google.oauth2 import service_account

from src.base import BackupDetails, BaseBackupDestinationManager, Credentials


class GCSBackupDestination(BaseBackupDestinationManager):
    """Google Cloud Storage backup destination.

    Credential mapping:
      url     — gs://bucket-name/optional/prefix
      api_key — service account JSON string (full contents of the .json key file)
                If omitted, falls back to Application Default Credentials.
      login   — unused
      password — unused
    """

    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self._bucket_name, self._prefix = self._parse_url(credentials.url)
        self._client = self._initialize_client()

    def _parse_url(self, url: str) -> tuple[str, str]:
        if not url.startswith("gs://"):
            raise ValueError("URL must start with gs://")
        path = url[len("gs://"):]
        parts = path.split("/", 1)
        bucket = parts[0]
        prefix = parts[1].rstrip("/") if len(parts) > 1 else ""
        if not bucket:
            raise ValueError("Bucket name is required")
        return bucket, prefix

    def _initialize_client(self) -> storage.Client:
        if self.credentials.api_key:
            info = json.loads(self.credentials.api_key)
            creds = service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            return storage.Client(credentials=creds, project=info.get("project_id"))
        return storage.Client()

    def _blob_name(self, filename: str) -> str:
        return f"{self._prefix}/{filename}" if self._prefix else filename

    def upload_backup(self, local_backup_path: str) -> str:
        if not os.path.exists(local_backup_path):
            raise FileNotFoundError(f"Backup file not found: {local_backup_path}")

        filename = os.path.basename(local_backup_path)
        blob_name = self._blob_name(filename)
        bucket = self._client.bucket(self._bucket_name)
        blob = bucket.blob(blob_name)

        # Avoid overwriting
        if blob.exists():
            from datetime import datetime
            name, ext = os.path.splitext(filename)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            blob_name = self._blob_name(f"{name}_{ts}{ext}")
            blob = bucket.blob(blob_name)

        blob.upload_from_filename(local_backup_path)
        return blob_name

    def list_backups(self) -> list[BackupDetails]:
        bucket = self._client.bucket(self._bucket_name)
        prefix = f"{self._prefix}/" if self._prefix else ""
        backups: list[BackupDetails] = []

        for blob in self._client.list_blobs(self._bucket_name, prefix=prefix):
            name = os.path.basename(blob.name)
            try:
                meta = self._parse_filename(name)
            except ValueError:
                continue

            backups.append(BackupDetails(
                name=name,
                path=blob.name,
                size=blob.size or 0,
                modified=blob.updated.isoformat() if blob.updated else "",
                source=meta["source"],
                tenant_id=meta["tenant_id"],
                schedule_id=meta["schedule_id"],
                source_id=meta["source_id"],
            ))

        backups.sort(key=lambda x: x.modified, reverse=True)
        return backups

    def delete_backup(self, backup_path: str) -> None:
        try:
            self._client.bucket(self._bucket_name).blob(backup_path).delete()
        except Exception as e:
            raise RuntimeError(f"GCS delete failed: {e}") from e

    def get_backup(self, backup_path: str, local_path: Optional[str] = None) -> str:
        if not local_path:
            local_path = str(uuid.uuid4()).replace("-", "")

        try:
            self._client.bucket(self._bucket_name).blob(backup_path).download_to_filename(local_path)
            return local_path
        except Exception as e:
            raise RuntimeError(f"GCS download failed: {e}") from e

    def _delete_extra_backups(self, keep_n: int = 5) -> None:
        backups = self.list_backups()
        for backup in backups[keep_n:]:
            try:
                self.delete_backup(backup.path)
            except Exception as e:
                print(f"Failed to delete backup {backup.path}: {e}")

    def test_connection(self) -> bool:
        try:
            bucket = self._client.bucket(self._bucket_name)
            bucket.exists()
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
