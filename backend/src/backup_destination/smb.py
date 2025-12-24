import os
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from src.base import Credentials, BaseBackupDestinationManager, BackupDetails

import smbclient
import smbclient.shutil


class SMBBackupDestination(BaseBackupDestinationManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.host, self.share, self.remote_dir = self._parse_smb_url(credentials.url)
        self._initialize_smb_session()

    def _parse_smb_url(self, url: str) -> tuple[str, str, str]:
        """Parse SMB URL to extract host, share, and remote directory

        Args:
            url: SMB URL in format smb://host/share/path or smb://host:port/share/path

        Returns:
            tuple: (host, share, remote_directory)
        """
        if not url.startswith("smb://"):
            raise ValueError("URL must start with smb://")

        # Remove smb:// prefix
        path = url[6:]

        # Split host and remaining path
        parts = path.split("/", 2)
        host_port = parts[0]
        share = parts[1] if len(parts) > 1 else None
        remote_dir = "/" + parts[2] if len(parts) > 2 else "/"

        # Extract host (ignore port if present, as it should be in credentials if needed)
        if ":" in host_port:
            host = host_port.rsplit(":", 1)[0]
        else:
            host = host_port

        if not host or not share:
            raise ValueError("Host and share are required in SMB URL (format: smb://host/share/path)")

        return host, share, remote_dir

    def _initialize_smb_session(self) -> None:
        """Initialize SMB session with provided credentials"""
        try:
            smbclient.register_session(
                self.host,
                username=self.credentials.login,
                password=self.credentials.password,
                auth_protocol="ntlm",
            )

            # Ensure remote directory exists
            smb_path = f"\\\\{self.host}\\{self.share}{self.remote_dir.replace('/', '\\')}"
            try:
                smbclient.mkdir(smb_path, exist_ok=True)
            except Exception:
                pass

        except Exception as e:
            raise RuntimeError(f"Failed to connect to SMB server: {str(e)}")

    def _get_smb_path(self, remote_path: str) -> str:
        """Convert remote path to SMB UNC path"""
        return f"\\\\{self.host}\\{self.share}{remote_path.replace('/', '\\')}"

    def upload_backup(self, local_backup_path: str) -> str:
        """Upload backup to SMB server

        Args:
            local_backup_path: Path to the local backup file to upload

        Returns:
            str: Remote path of the uploaded backup
        """
        if not os.path.exists(local_backup_path):
            raise FileNotFoundError(f"Backup file not found: {local_backup_path}")

        filename = os.path.basename(local_backup_path)
        remote_path = f"{self.remote_dir}/{filename}".replace("//", "/")

        try:
            smb_path = self._get_smb_path(remote_path)
            smbclient.shutil.copy(local_backup_path, smb_path)
            return remote_path
        except Exception as e:
            raise RuntimeError(f"Failed to upload backup to SMB: {str(e)}")

    def list_backups(self) -> list[BackupDetails]:
        """List all backups stored on SMB server

        Returns:
            list[BackupDetails]: List of backup details
        """
        backups = []

        try:
            smb_path = self._get_smb_path(self.remote_dir)

            # List files in remote directory
            for entry in smbclient.listdir(smb_path):
                if entry.startswith("."):
                    continue

                file_path = f"{smb_path}\\{entry}"
                remote_path = f"{self.remote_dir}/{entry}".replace("//", "/")

                try:
                    # Get file stats
                    stat_info = smbclient.stat(file_path)

                    # Skip if it's a directory
                    if stat_info.is_dir():
                        continue

                    backup = BackupDetails(
                        name=entry,
                        path=remote_path,
                        size=stat_info.st_size,
                        modified=datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                    )
                    backups.append(backup)
                except Exception:
                    continue

            # Sort by modification time (newest first)
            backups.sort(key=lambda x: x.modified, reverse=True)

        except Exception as e:
            raise RuntimeError(f"Failed to list backups from SMB: {str(e)}")

        return backups

    def delete_backup(self, backup_path: str) -> None:
        """Delete specified backup from SMB server

        Args:
            backup_path: Remote path of the backup to delete
        """
        try:
            smb_path = self._get_smb_path(backup_path)
            smbclient.remove(smb_path)
        except Exception as e:
            raise RuntimeError(f"Failed to delete backup from SMB: {str(e)}")

    def get_backup(self, backup_path: str, local_path: Optional[str] = None) -> str:
        """Download/retrieve specified backup from SMB server

        Args:
            backup_path: Remote path of the backup to retrieve
            local_path: Optional local path where backup should be saved.
                       If not provided, a random path will be generated.

        Returns:
            str: Path to the downloaded backup file
        """
        if not local_path:
            local_path = str(uuid.uuid4()).replace("-", "")

        try:
            smb_path = self._get_smb_path(backup_path)
            smbclient.shutil.copy(smb_path, local_path)
            return local_path
        except Exception as e:
            raise RuntimeError(f"Failed to download backup from SMB: {str(e)}")

    def _delete_extra_backups(self, keep_n: int = 5) -> None:
        """Delete extra backups from SMB server, keeping only the most recent N

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
        """Test whether the SMB server is accessible

        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            smb_path = self._get_smb_path(self.remote_dir)
            smbclient.listdir(smb_path)
            return True
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False