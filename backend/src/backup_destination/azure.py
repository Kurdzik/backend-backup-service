import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError

from src.base import BackupDetails, BaseBackupDestinationManager, Credentials


class AzureBackupDestination(BaseBackupDestinationManager):
    """Azure Blob Storage backup destination.

    Credential mapping:
      url      — azure://container-name/optional/prefix
      login    — storage account name
      password — storage account key
      api_key  — full connection string (overrides login+password if provided)
    """

    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self._container, self._prefix = self._parse_url(credentials.url)
        self._client = self._initialize_client()

    def _parse_url(self, url: str) -> tuple[str, str]:
        if not url.startswith("azure://"):
            raise ValueError("URL must start with azure://")
        path = url[len("azure://"):]
        parts = path.split("/", 1)
        container = parts[0]
        prefix = parts[1].rstrip("/") if len(parts) > 1 else ""
        if not container:
            raise ValueError("Container name is required")
        return container, prefix

    def _initialize_client(self) -> BlobServiceClient:
        if self.credentials.api_key:
            return BlobServiceClient.from_connection_string(self.credentials.api_key)
        account = self.credentials.login
        key = self.credentials.password
        if not account or not key:
            raise ValueError(
                "Either api_key (connection string) or login+password "
                "(account name + key) are required"
            )
        account_url = f"https://{account}.blob.core.windows.net"
        return BlobServiceClient(account_url=account_url, credential=key)

    def _blob_name(self, filename: str) -> str:
        return f"{self._prefix}/{filename}" if self._prefix else filename

    def upload_backup(self, local_backup_path: str) -> str:
        if not os.path.exists(local_backup_path):
            raise FileNotFoundError(f"Backup file not found: {local_backup_path}")

        filename = os.path.basename(local_backup_path)
        blob_name = self._blob_name(filename)
        container_client = self._client.get_container_client(self._container)

        # Avoid overwriting — append timestamp if blob already exists
        try:
            container_client.get_blob_client(blob_name).get_blob_properties()
            name, ext = os.path.splitext(filename)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            blob_name = self._blob_name(f"{name}_{ts}{ext}")
        except ResourceNotFoundError:
            pass

        with open(local_backup_path, "rb") as data:
            container_client.upload_blob(name=blob_name, data=data, overwrite=False)

        return blob_name

    def list_backups(self) -> list[BackupDetails]:
        container_client = self._client.get_container_client(self._container)
        prefix = f"{self._prefix}/" if self._prefix else ""
        backups: list[BackupDetails] = []

        for blob in container_client.list_blobs(name_starts_with=prefix):
            name = os.path.basename(blob.name)
            try:
                meta = self._parse_filename(name)
            except ValueError:
                continue

            modified = blob.last_modified
            if modified and modified.tzinfo is None:
                modified = modified.replace(tzinfo=timezone.utc)

            backups.append(BackupDetails(
                name=name,
                path=blob.name,
                size=blob.size or 0,
                modified=modified.isoformat() if modified else "",
                source=meta["source"],
                tenant_id=meta["tenant_id"],
                schedule_id=meta["schedule_id"],
                source_id=meta["source_id"],
            ))

        backups.sort(key=lambda x: x.modified, reverse=True)
        return backups

    def delete_backup(self, backup_path: str) -> None:
        try:
            self._client.get_blob_client(
                container=self._container, blob=backup_path
            ).delete_blob()
        except Exception as e:
            raise RuntimeError(f"Azure delete failed: {e}") from e

    def get_backup(self, backup_path: str, local_path: Optional[str] = None) -> str:
        if not local_path:
            local_path = str(uuid.uuid4()).replace("-", "")

        try:
            blob_client = self._client.get_blob_client(
                container=self._container, blob=backup_path
            )
            with open(local_path, "wb") as f:
                f.write(blob_client.download_blob().readall())
            return local_path
        except ResourceNotFoundError:
            raise FileNotFoundError(f"Backup not found in Azure: {backup_path}")
        except Exception as e:
            raise RuntimeError(f"Azure download failed: {e}") from e

    def _delete_extra_backups(self, keep_n: int = 5) -> None:
        backups = self.list_backups()
        for backup in backups[keep_n:]:
            try:
                self.delete_backup(backup.path)
            except Exception as e:
                print(f"Failed to delete backup {backup.path}: {e}")

    def test_connection(self) -> bool:
        try:
            container_client = self._client.get_container_client(self._container)
            container_client.exists()
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
