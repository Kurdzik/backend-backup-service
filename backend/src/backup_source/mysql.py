import os
import subprocess
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import mysql.connector

from src.base import BaseBackupManager, Credentials


class MySQLBackupManager(BaseBackupManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.connection_params = self._parse_connection_params()

    def _parse_connection_params(self) -> dict:
        parsed_url = urlparse(self.credentials.url)

        return {
            "host": parsed_url.hostname or "localhost",
            "port": parsed_url.port or 3306,
            "user": self.credentials.login or parsed_url.username or "root",
            "password": self.credentials.password or parsed_url.password or "",
            "database": parsed_url.path.lstrip("/") or "",
        }

    def create_backup(
        self, tenant_id: str, backup_source_id: int, schedule_id: Optional[int] = None
    ) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"mysql_backup_usr={tenant_id}_sch={schedule_id}_src={backup_source_id}_created_at={timestamp}.sql"

        cmd = [
            "mysqldump",
            f"--host={self.connection_params['host']}",
            f"--port={self.connection_params['port']}",
            f"--user={self.connection_params['user']}",
            f"--password={self.connection_params['password']}",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--result-file",
            backup_path,
        ]

        database = self.connection_params.get("database")
        if database:
            cmd.append(database)
        else:
            cmd.append("--all-databases")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )

            if not os.path.exists(backup_path):
                raise RuntimeError(f"Backup file was not created: {result.stderr}")

            return backup_path

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"mysqldump failed: {e.stderr}")

    def restore_from_backup(self, backup_path: str) -> None:
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        cmd = [
            "mysql",
            f"--host={self.connection_params['host']}",
            f"--port={self.connection_params['port']}",
            f"--user={self.connection_params['user']}",
            f"--password={self.connection_params['password']}",
        ]

        database = self.connection_params.get("database")
        if database:
            cmd.append(database)

        try:
            with open(backup_path, "r") as f:
                subprocess.run(
                    cmd, stdin=f, capture_output=True, text=True, check=True
                )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"mysql restore failed: {e.stderr}")

    def test_connection(self) -> bool:
        try:
            params = {
                "host": self.connection_params["host"],
                "port": self.connection_params["port"],
                "user": self.connection_params["user"],
                "password": self.connection_params["password"],
            }
            database = self.connection_params.get("database")
            if database:
                params["database"] = database

            conn = mysql.connector.connect(**params)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
