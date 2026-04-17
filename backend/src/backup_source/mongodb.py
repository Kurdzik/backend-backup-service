import os
import subprocess
from datetime import datetime
from typing import Optional

import pymongo

from src.base import BaseBackupManager, Credentials


class MongoDBBackupManager(BaseBackupManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)

    def _build_uri(self) -> str:
        """Build a MongoDB URI from credentials.

        Accepts either a full mongodb:// URI in credentials.url, or a plain
        host[:port] with optional login/password fields.
        """
        url = self.credentials.url
        if url.startswith("mongodb://") or url.startswith("mongodb+srv://"):
            return url

        host = url.rstrip("/")
        if self.credentials.login and self.credentials.password:
            return f"mongodb://{self.credentials.login}:{self.credentials.password}@{host}"
        return f"mongodb://{host}"

    def create_backup(
        self, tenant_id: str, backup_source_id: int, schedule_id: Optional[int] = None
    ) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"mongodb_backup_usr={tenant_id}_sch={schedule_id}_src={backup_source_id}_created_at={timestamp}.archive.gz"

        cmd = [
            "mongodump",
            f"--uri={self._build_uri()}",
            "--gzip",
            f"--archive={backup_path}",
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )

            if not os.path.exists(backup_path):
                raise RuntimeError(f"Backup file was not created: {result.stderr}")

            return backup_path

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"mongodump failed: {e.stderr}")

    def restore_from_backup(self, backup_path: str) -> None:
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        cmd = [
            "mongorestore",
            f"--uri={self._build_uri()}",
            "--gzip",
            f"--archive={backup_path}",
            "--drop",
        ]

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"mongorestore failed: {e.stderr}")

    def test_connection(self) -> bool:
        try:
            client = pymongo.MongoClient(self._build_uri(), serverSelectionTimeoutMS=5000)
            client.server_info()
            client.close()
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
