import os
import re
import subprocess
from datetime import datetime
from typing import Optional

from src.base import BaseBackupManager, Credentials


import psycopg2
from psycopg2 import sql
import subprocess
import os
from datetime import datetime
from urllib.parse import urlparse


class PostgresBackupManager(BaseBackupManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.connection_params = self._parse_connection_params()

    def _parse_connection_params(self) -> dict:
        """Parse connection parameters from credentials

        Returns:
            dict: Connection parameters for psycopg2
        """
        parsed_url = urlparse(self.credentials.url)

        params = {
            "host": parsed_url.hostname or "localhost",
            "port": parsed_url.port or 5432,
            "user": self.credentials.login or parsed_url.username or "postgres",
            "password": self.credentials.password or parsed_url.password,
            "database": parsed_url.path.lstrip("/") or "postgres",
        }

        return {k: v for k, v in params.items() if v is not None}

    def create_backup(self) -> str:
        """Create backup of all Postgres databases using pg_dump

        Returns:
            str: Path to the locally created backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"postgres_backup_{timestamp}.sql"

        # Build pg_dump command
        env = os.environ.copy()
        if self.connection_params.get("password"):
            env["PGPASSWORD"] = self.connection_params["password"]

        cmd = [
            "pg_dump",
            "-h",
            self.connection_params.get("host", "localhost"),
            "-p",
            str(self.connection_params.get("port", 5432)),
            "-U",
            self.connection_params.get("user", "postgres"),
            "-F",
            "c",  # Custom format for better compression and restoration
            "-v",
            "-f",
            backup_path,
            self.connection_params.get("database", "postgres"),
        ]

        try:
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, check=True
            )

            if not os.path.exists(backup_path):
                raise RuntimeError(f"Backup file was not created: {result.stderr}")

            return backup_path

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"pg_dump failed: {e.stderr}")

    def restore_from_backup(self, backup_path: str, backup_destination: str) -> None:
        """Restore Postgres database from backup using pg_restore

        Args:
            backup_path: Path to the backup file
            backup_destination: Target database name to restore to
        """
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        # Build pg_restore command
        env = os.environ.copy()
        if self.connection_params.get("password"):
            env["PGPASSWORD"] = self.connection_params["password"]

        cmd = [
            "pg_restore",
            "-h",
            self.connection_params.get("host", "localhost"),
            "-p",
            str(self.connection_params.get("port", 5432)),
            "-U",
            self.connection_params.get("user", "postgres"),
            "-d",
            backup_destination,
            "-v",
            backup_path,
        ]

        try:
            # Drop target database if it exists
            try:
                conn = psycopg2.connect(**self.connection_params)
                conn.autocommit = True
                cursor = conn.cursor()
                cursor.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {} CASCADE").format(
                        sql.Identifier(backup_destination)
                    )
                )
                cursor.close()
                conn.close()
            except Exception:
                pass

            # Create target database
            conn = psycopg2.connect(**self.connection_params)
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(backup_destination))
            )
            cursor.close()
            conn.close()

            # Restore backup
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, check=True
            )

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"pg_restore failed: {e.stderr}")
        except psycopg2.Error as e:
            raise RuntimeError(f"Database operation failed: {str(e)}")

    def test_connection(self) -> bool:
        """Test whether the Postgres database is reachable
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            conn = psycopg2.connect(**self.connection_params)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            return True
        except psycopg2.Error as e:
            print(f"Connection test failed: {str(e)}")
            return False
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False