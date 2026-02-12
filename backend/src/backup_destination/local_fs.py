import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from src.base import BackupDetails, BaseBackupDestinationManager, Credentials


class LocalFSBackupDestination(BaseBackupDestinationManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.backup_dir = credentials.url
        self._ensure_backup_dir_exists()

    def _ensure_backup_dir_exists(self) -> None:
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)

    def upload_backup(self, local_backup_path: str) -> str:
        if not os.path.exists(local_backup_path):
            raise FileNotFoundError(f"Backup file not found: {local_backup_path}")

        # Generate destination filename with timestamp
        filename = os.path.basename(local_backup_path)
        destination_path = os.path.join(self.backup_dir, filename)

        # If file already exists, append timestamp to avoid conflicts
        if os.path.exists(destination_path):
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}{ext}"
            destination_path = os.path.join(self.backup_dir, filename)

        # Copy file to backup directory
        shutil.copy2(local_backup_path, destination_path)

        return destination_path

    def list_backups(self) -> list[BackupDetails]:
        backups = []

        if not os.path.exists(self.backup_dir):
            return backups

        for filename in os.listdir(self.backup_dir):
            filepath = os.path.join(self.backup_dir, filename)

            # Skip directories
            if os.path.isdir(filepath):
                continue

            # Get file stats
            stat_info = os.stat(filepath)
            size = stat_info.st_size
            modified = datetime.fromtimestamp(stat_info.st_mtime).isoformat()

            backup = BackupDetails(
                name=filename,
                path=filepath,
                size=size,
                modified=modified,
                source=self._parse_filename(filepath)["source"],
                tenant_id=self._parse_filename(filepath)["tenant_id"],
                schedule_id=self._parse_filename(filepath)["schedule_id"],
                source_id=self._parse_filename(filepath)["source_id"],
            )
            backups.append(backup)

        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x.modified, reverse=True)

        return backups

    def delete_backup(self, backup_path: str) -> None:
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        if not backup_path.startswith(self.backup_dir):
            raise ValueError(f"Backup path is outside backup directory: {backup_path}")

        os.remove(backup_path)

    def get_backup(self, backup_path: str, local_path: Optional[str] = None) -> str:
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        if not backup_path.startswith(self.backup_dir):
            raise ValueError(f"Backup path is outside backup directory: {backup_path}")

        if not local_path:
            import uuid

            local_path = str(uuid.uuid4()).replace("-", "")

        # Copy backup to local path
        shutil.copy2(backup_path, local_path)

        return local_path

    def _delete_extra_backups(self, keep_n: int = 5) -> None:
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
        try:
            # Check if directory exists and is accessible
            if not os.path.exists(self.backup_dir):
                print(f"Backup directory does not exist: {self.backup_dir}")
                return False

            # Check if directory is readable
            if not os.access(self.backup_dir, os.R_OK):
                print(f"Backup directory is not readable: {self.backup_dir}")
                return False

            # Check if directory is writable
            if not os.access(self.backup_dir, os.W_OK):
                print(f"Backup directory is not writable: {self.backup_dir}")
                return False

            return True
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False
