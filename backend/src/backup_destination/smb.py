import os
import uuid
import tempfile
from datetime import datetime
from typing import Optional

import smbclient
import smbclient.shutil

from src.base import Credentials, BaseBackupDestinationManager, BackupDetails


class SMBBackupDestination(BaseBackupDestinationManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.host, self.share, self.remote_dir = self._parse_smb_url(credentials.url)
        self._initialize_smb_session()

    def _parse_smb_url(self, url: str) -> tuple[str, str, str]:
        if not url.startswith("smb://"):
            raise ValueError("URL must start with smb://")

        path = url[6:]
        parts = path.split("/", 2)

        host_port = parts[0]
        share = parts[1] if len(parts) > 1 else None
        remote_dir = "/" + parts[2] if len(parts) > 2 else "/"

        host = host_port.split(":", 1)[0]

        if not host or not share:
            raise ValueError("SMB URL must be smb://host/share/path")

        return host, share, remote_dir.rstrip("/")

    def _initialize_smb_session(self) -> None:
        try:
            smbclient.register_session(
                self.host,
                username=self.credentials.login,
                password=self.credentials.password,
                auth_protocol="ntlm",
            )
            self._ensure_remote_dir(self.remote_dir)
        except Exception as e:
            raise RuntimeError(f"Failed to connect to SMB server: {e}") from e

    def _ensure_remote_dir(self, remote_dir: str) -> None:
        """Recursively create SMB directories"""
        parts = remote_dir.strip("/").split("/")
        current = ""
        for part in parts:
            current += f"/{part}"
            smb_path = self._get_smb_path(current)
            try:
                smbclient.stat(smb_path)
            except Exception:
                try:
                    smbclient.mkdir(smb_path)
                except Exception:
                    pass

    def _get_smb_path(self, remote_path: str) -> str:
        normalized = remote_path.replace("/", "\\")
        return f"\\\\{self.host}\\{self.share}{normalized}"

    def upload_backup(self, local_backup_path: str) -> str:
        if not os.path.exists(local_backup_path):
            raise FileNotFoundError(local_backup_path)

        filename = os.path.basename(local_backup_path)
        unique_name = f"{uuid.uuid4().hex}_{filename}"

        final_remote = f"{self.remote_dir}/{unique_name}"
        temp_remote = f"{final_remote}.tmp"

        temp_smb = self._get_smb_path(temp_remote)
        final_smb = self._get_smb_path(final_remote)

        try:
            smbclient.shutil.copy(local_backup_path, temp_smb)
            smbclient.rename(temp_smb, final_smb)
            return final_remote
        except Exception as e:
            try:
                smbclient.remove(temp_smb)
            except Exception:
                pass
            raise RuntimeError(f"SMB upload failed: {e}") from e

    def list_backups(self) -> list[BackupDetails]:
        backups: list[BackupDetails] = []

        try:
            smb_dir = self._get_smb_path(self.remote_dir)

            for entry in smbclient.listdir(smb_dir):
                if not entry or entry.endswith(".tmp"):
                    continue

                smb_file = f"{smb_dir}\\{entry}"
                remote_path = f"{self.remote_dir}/{entry}"

                try:
                    stat = smbclient.stat(smb_file)
                    if stat.is_dir():
                        continue

                    meta = self._parse_filename(entry)

                    backups.append(
                        BackupDetails(
                            name=entry,
                            path=remote_path,
                            size=stat.st_size,
                            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            source=meta["source"],
                            tenant_id=meta["tenant_id"],
                            schedule_id=meta["schedule_id"],
                            source_id=meta["source_id"],
                        )
                    )
                except Exception:
                    continue

            backups.sort(key=lambda b: b.modified, reverse=True)
            return backups

        except Exception as e:
            raise RuntimeError(f"Failed to list SMB backups: {e}") from e

    def delete_backup(self, backup_path: str) -> None:
        try:
            smbclient.remove(self._get_smb_path(backup_path))
        except Exception as e:
            raise RuntimeError(f"SMB delete failed: {e}") from e

    def get_backup(self, backup_path: str, local_path: Optional[str] = None) -> str:
        if not local_path:
            fd, local_path = tempfile.mkstemp(prefix="smb_restore_")
            os.close(fd)

        try:
            smbclient.shutil.copy(self._get_smb_path(backup_path), local_path)
            return local_path
        except Exception as e:
            raise RuntimeError(f"SMB download failed: {e}") from e

    def test_connection(self) -> bool:
        try:
            smbclient.listdir(self._get_smb_path(self.remote_dir))
            return True
        except Exception:
            return False
