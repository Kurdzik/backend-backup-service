import os
import stat
import tempfile
from datetime import datetime
from typing import Optional

import paramiko

from src.base import BackupDetails, BaseBackupDestinationManager, Credentials


class SFTPBackupDestination(BaseBackupDestinationManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.host, self.port, self.remote_dir = self._parse_sftp_url(credentials.url)

        self._ssh_client: Optional[paramiko.SSHClient] = None
        self.sftp_client = self._initialize_sftp_client()

    def _parse_sftp_url(self, url: str) -> tuple[str, int, str]:
        if url.startswith("sftp://"):
            url = url[7:]
            
        parts = [p for p in url.split("/") if p]
        if not parts:
            raise ValueError("Host is required in SFTP URL")

        host_port = parts[0]
        remote_dir = "/" + "/".join(parts[1:]) if len(parts) > 1 else "/"

        port = 22
        if ":" in host_port:
            host, port_str = host_port.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                raise ValueError("Invalid port in SFTP URL")
        else:
            host = host_port

        if not host:
            raise ValueError("Host is required in SFTP URL")

        return host, port, remote_dir

    def _initialize_sftp_client(self) -> paramiko.SFTPClient:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.credentials.login,
                password=self.credentials.password,
                timeout=10,
            )

            self._ssh_client = ssh
            sftp = ssh.open_sftp()

            self._ensure_remote_dir(sftp, self.remote_dir)
            return sftp

        except Exception as e:
            raise RuntimeError(f"Failed to connect to SFTP server: {e}") from e

    def _ensure_remote_dir(self, sftp: paramiko.SFTPClient, path: str) -> None:
        if path == "/":
            return
            
        parts = [p for p in path.split("/") if p]
        current = ""
        for part in parts:
            current += "/" + part
            try:
                sftp.stat(current)
            except IOError:
                try:
                    sftp.mkdir(current)
                except Exception as e:
                    print(f"Failed to create remote directory {current}: {e}")

    def upload_backup(self, local_backup_path: str) -> str:
        if not os.path.exists(local_backup_path):
            raise FileNotFoundError(f"Backup file not found: {local_backup_path}")

        filename = os.path.basename(local_backup_path)
        final_remote = f"{self.remote_dir}/{filename}"

        file_exists = False
        try:
            self.sftp_client.stat(final_remote)
            file_exists = True
        except IOError:
            pass

        if file_exists:
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}{ext}"
            final_remote = f"{self.remote_dir}/{filename}"

        temp_remote = f"{final_remote}.tmp"

        try:
            self.sftp_client.put(local_backup_path, temp_remote)
            self.sftp_client.rename(temp_remote, final_remote)
            return final_remote
        except Exception as e:
            try:
                self.sftp_client.remove(temp_remote)
            except Exception:
                pass
            raise RuntimeError(f"SFTP upload failed: {e}") from e

    def list_backups(self) -> list[BackupDetails]:
        backups: list[BackupDetails] = []

        try:
            for attr in self.sftp_client.listdir_attr(self.remote_dir):
                if stat.S_ISDIR(attr.st_mode):
                    continue

                if not attr.filename or attr.filename.endswith(".tmp"):
                    continue

                remote_path = f"{self.remote_dir}/{attr.filename}"
                meta = self._parse_filename(attr.filename)

                backups.append(
                    BackupDetails(
                        name=attr.filename,
                        path=remote_path,
                        size=attr.st_size,
                        modified=datetime.fromtimestamp(attr.st_mtime).isoformat(),
                        source=meta["source"],
                        tenant_id=meta["tenant_id"],
                        schedule_id=meta["schedule_id"],
                        source_id=meta["source_id"],
                    )
                )

            backups.sort(key=lambda b: b.modified, reverse=True)
            return backups

        except Exception as e:
            raise RuntimeError(f"Failed to list backups from SFTP: {e}") from e

    def delete_backup(self, backup_path: str) -> None:
        try:
            self.sftp_client.remove(backup_path)
        except Exception as e:
            raise RuntimeError(f"SFTP delete failed: {e}") from e

    def get_backup(self, backup_path: str, local_path: Optional[str] = None) -> str:
        if not local_path:
            fd, local_path = tempfile.mkstemp(prefix="sftp_restore_")
            os.close(fd)

        try:
            self.sftp_client.get(backup_path, local_path)
            return local_path
        except Exception as e:
            raise RuntimeError(f"SFTP download failed: {e}") from e

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
            self.sftp_client.stat(self.remote_dir)
            return True
        except Exception as e:
            print(f"SFTP Connection test failed: {str(e)}")
            return False

    def close(self) -> None:
        try:
            if self.sftp_client:
                self.sftp_client.close()
            if self._ssh_client:
                self._ssh_client.close()
        except Exception:
            pass