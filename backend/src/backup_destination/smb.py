import os
import stat
import tempfile
from datetime import datetime
from typing import Optional

import smbclient
import smbclient.shutil

from src.base import BackupDetails, BaseBackupDestinationManager, Credentials


class SMBBackupDestination(BaseBackupDestinationManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.host, self.share, self.remote_dir = self._parse_smb_url(credentials.url)
        self._initialize_smb_session()

    def _parse_smb_url(self, url: str) -> tuple[str, str, str]:
        normalized_url = url.replace("\\", "/")
        
        if normalized_url.startswith("smb://"):
            path = normalized_url[6:]
        elif normalized_url.startswith("//"):
            path = normalized_url[2:]
        else:
            path = normalized_url

        parts = [p for p in path.split("/") if p]
        
        if len(parts) < 2:
            raise ValueError("SMB URL must contain at least a host and a share (e.g., //server/share)")

        host = parts[0].split(":", 1)[0]  # Remove port if accidentally provided
        share = parts[1]
        remote_dir = "/" + "/".join(parts[2:]) if len(parts) > 2 else "/"

        return host, share, remote_dir

    def _initialize_smb_session(self) -> None:
        try:
            smbclient.register_session(
                self.host,
                username=self.credentials.login,
                password=self.credentials.password,
            )
            self._ensure_remote_dir(self.remote_dir)
        except Exception as e:
            raise RuntimeError(f"Failed to connect to SMB server {self.host}: {e}") from e

    def _ensure_remote_dir(self, remote_dir: str) -> None:
        if remote_dir == "/":
            return
            
        parts = [p for p in remote_dir.split("/") if p]
        current = ""
        for part in parts:
            current += f"/{part}"
            smb_path = self._get_smb_path(current)
            try:
                smbclient.stat(smb_path)
            except Exception:
                try:
                    smbclient.mkdir(smb_path)
                except Exception as e:
                    print(f"Failed to create remote directory {smb_path}: {e}")

    def _get_smb_path(self, remote_path: str) -> str:
        normalized = remote_path.replace("/", "\\")
        if not normalized.startswith("\\"):
            normalized = "\\" + normalized
        return f"\\\\{self.host}\\{self.share}{normalized}"

    def upload_backup(self, local_backup_path: str) -> str:
        if not os.path.exists(local_backup_path):
            raise FileNotFoundError(f"Backup file not found: {local_backup_path}")

        filename = os.path.basename(local_backup_path)
        final_remote = f"{self.remote_dir.rstrip('/')}/{filename}"
        final_smb = self._get_smb_path(final_remote)

        file_exists = False
        try:
            smbclient.stat(final_smb)
            file_exists = True
        except Exception:
            pass

        if file_exists:
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}{ext}"
            final_remote = f"{self.remote_dir.rstrip('/')}/{filename}"
            final_smb = self._get_smb_path(final_remote)

        temp_remote = f"{final_remote}.tmp"
        temp_smb = self._get_smb_path(temp_remote)

        try:
            smbclient.shutil.copyfile(local_backup_path, temp_smb)
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
                remote_path = f"{self.remote_dir.rstrip('/')}/{entry}"

                try:
                    file_stat = smbclient.stat(smb_file)
                    if stat.S_ISDIR(file_stat.st_mode):
                        continue

                    meta = self._parse_filename(entry)

                    backups.append(
                        BackupDetails(
                            name=entry,
                            path=remote_path,
                            size=file_stat.st_size,
                            modified=datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
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
            smbclient.shutil.copyfile(self._get_smb_path(backup_path), local_path)
            return local_path
        except Exception as e:
            raise RuntimeError(f"SMB download failed: {e}") from e

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
            smbclient.listdir(self._get_smb_path(self.remote_dir))
            return True
        except Exception as e:
            print(f"SMB Connection test failed: {str(e)}")
            return False