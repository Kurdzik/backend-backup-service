import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import paramiko

from src.base import BackupDetails, BaseBackupDestinationManager, Credentials


class SFTPBackupDestination(BaseBackupDestinationManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.host, self.remote_dir = self._parse_sftp_url(credentials.url)
        self.port = 22
        self.sftp_client = self._initialize_sftp_client()

    def _parse_sftp_url(self, url: str) -> tuple[str, str]:
        """Parse SFTP URL to extract host and remote directory

        Args:
            url: SFTP URL in format sftp://host/path or sftp://host:port/path

        Returns:
            tuple: (host, remote_directory)
        """
        if not url.startswith("sftp://"):
            raise ValueError("URL must start with sftp://")

        # Remove sftp:// prefix
        path = url[7:]

        # Split host and path
        parts = path.split("/", 1)
        host_port = parts[0]
        remote_dir = "/" + parts[1] if len(parts) > 1 else "/"

        # Extract host and port
        if ":" in host_port:
            host, port_str = host_port.rsplit(":", 1)
            try:
                self.port = int(port_str)
            except ValueError:
                host = host_port
        else:
            host = host_port

        if not host:
            raise ValueError("Host is required in SFTP URL")

        return host, remote_dir

    def _initialize_sftp_client(self) -> paramiko.SFTPClient:
        """Initialize SFTP client with provided credentials

        Returns:
            paramiko.SFTPClient: Connected SFTP client
        """
        try:
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Connect with credentials
            ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.credentials.login,
                password=self.credentials.password,
            )

            # Open SFTP session
            sftp = ssh.open_sftp()

            # Ensure remote directory exists
            try:
                sftp.stat(self.remote_dir)
            except IOError:
                sftp.mkdir(self.remote_dir)

            return sftp

        except Exception as e:
            raise RuntimeError(f"Failed to connect to SFTP server: {str(e)}")

    def upload_backup(self, local_backup_path: str) -> str:
        """Upload backup to SFTP server

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
            self.sftp_client.put(local_backup_path, remote_path)
            return remote_path
        except Exception as e:
            raise RuntimeError(f"Failed to upload backup to SFTP: {str(e)}")

    def list_backups(self) -> list[BackupDetails]:
        """List all backups stored on SFTP server

        Returns:
            list[BackupDetails]: List of backup details
        """
        backups = []

        try:
            # List files in remote directory
            file_attrs = self.sftp_client.listdir_attr(self.remote_dir)

            for attr in file_attrs:
                # Skip directories
                if attr.filename.startswith("."):
                    continue

                remote_path = f"{self.remote_dir}/{attr.filename}".replace("//", "/")

                backup = BackupDetails(
                    name=attr.filename,
                    path=remote_path,
                    size=attr.st_size,
                    modified=datetime.fromtimestamp(attr.st_mtime).isoformat(),
                    source=self._parse_filename(attr.filename)["source"],
                    tenant_id=self._parse_filename(attr.filename)["tenant_id"],
                    schedule_id=self._parse_filename(attr.filename)["schedule_id"],
                    source_id=self._parse_filename(attr.filename)["source_id"],

                )
                backups.append(backup)

            # Sort by modification time (newest first)
            backups.sort(key=lambda x: x.modified, reverse=True)

        except Exception as e:
            raise RuntimeError(f"Failed to list backups from SFTP: {str(e)}")

        return backups

    def delete_backup(self, backup_path: str) -> None:
        """Delete specified backup from SFTP server

        Args:
            backup_path: Remote path of the backup to delete
        """
        try:
            self.sftp_client.remove(backup_path)
        except Exception as e:
            raise RuntimeError(f"Failed to delete backup from SFTP: {str(e)}")

    def get_backup(self, backup_path: str, local_path: Optional[str] = None) -> str:
        """Download/retrieve specified backup from SFTP server

        Args:
            backup_path: Remote path of the backup to retrieve
            local_path: Optional local path where backup should be saved.
                       If not provided, a random path will be generated.

        Returns:
            str: Path to the downloaded backup file
        """
        if not local_path:
            import uuid

            local_path = str(uuid.uuid4()).replace("-", "")

        try:
            self.sftp_client.get(backup_path, local_path)
            return local_path
        except Exception as e:
            raise RuntimeError(f"Failed to download backup from SFTP: {str(e)}")

    def _delete_extra_backups(self, keep_n: int = 5) -> None:
        """Delete extra backups from SFTP server, keeping only the most recent N

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
        """Test whether the SFTP server is accessible

        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            # Attempt to access the remote directory
            # This verifies both connectivity and access to the configured path
            self.sftp_client.stat(self.remote_dir)
            return True
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False
