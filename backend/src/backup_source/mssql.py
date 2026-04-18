import os
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import pyodbc

from src.base import BaseBackupManager, Credentials


class MSSQLBackupManager(BaseBackupManager):
    """Logical backup for SQL Server via pyodbc.

    BACKUP DATABASE writes to the server's local disk so cannot be used
    remotely. Instead we generate a logical dump (CREATE TABLE + INSERT
    statements) by querying the information schema — similar to mysqldump.

    System requirement: the ODBC Driver for SQL Server must be installed on
    the host (msodbcsql18 on Linux, or equivalent).
    """

    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self._params = self._parse_url()
        self._conn_str = self._build_conn_str()

    def _parse_url(self) -> dict:
        url = self.credentials.url
        if not url.startswith("mssql://"):
            url = f"mssql://{url}"
        parsed = urlparse(url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 1433,
            "database": parsed.path.lstrip("/") or "master",
        }

    def _build_conn_str(self) -> str:
        p = self._params
        user = self.credentials.login or "sa"
        pwd = self.credentials.password or ""
        return (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={p['host']},{p['port']};"
            f"DATABASE={p['database']};"
            f"UID={user};PWD={pwd};"
            f"TrustServerCertificate=yes;"
        )

    # ------------------------------------------------------------------ #

    def _connect(self) -> pyodbc.Connection:
        return pyodbc.connect(self._conn_str, timeout=10)

    def _has_identity(self, cursor, table: str) -> bool:
        cursor.execute(
            "SELECT COUNT(*) FROM sys.identity_columns ic "
            "JOIN sys.tables t ON ic.object_id = t.object_id "
            "WHERE t.name = ?",
            table,
        )
        return cursor.fetchone()[0] > 0

    def _create_table_ddl(self, cursor, table: str) -> str:
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
                   NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE,
                   COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """,
            table,
        )
        cols = cursor.fetchall()
        col_defs = []
        for col in cols:
            name, dtype, char_len, num_prec, num_scale, nullable, default = col
            type_str = dtype.upper()
            if char_len and char_len != -1:
                type_str += f"({char_len})"
            elif char_len == -1:
                type_str += "(MAX)"
            elif dtype.lower() in ("decimal", "numeric") and num_prec is not None:
                type_str += f"({num_prec},{num_scale or 0})"
            null_str = "NULL" if nullable == "YES" else "NOT NULL"
            default_str = f" DEFAULT {default}" if default else ""
            col_defs.append(f"    [{name}] {type_str}{default_str} {null_str}")
        return f"CREATE TABLE [{table}] (\n" + ",\n".join(col_defs) + "\n);"

    def _quote_value(self, v) -> str:
        if v is None:
            return "NULL"
        if isinstance(v, bool):
            return "1" if v else "0"
        if isinstance(v, (int, float)):
            return str(v)
        return "'" + str(v).replace("'", "''") + "'"

    def create_backup(
        self, tenant_id: str, backup_source_id: int, schedule_id: Optional[int] = None
    ) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = (
            f"mssql_backup_usr={tenant_id}_sch={schedule_id}"
            f"_src={backup_source_id}_created_at={timestamp}.sql"
        )

        conn = self._connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
            )
            tables = [r[0] for r in cursor.fetchall()]

            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(f"-- MSSQL logical backup\n")
                f.write(f"-- Database: {self._params['database']}\n")
                f.write(f"-- Created: {datetime.now().isoformat()}\n\n")
                f.write("SET NOCOUNT ON;\nGO\n\n")

                for table in tables:
                    f.write(f"-- Table: {table}\n")
                    f.write(f"IF OBJECT_ID(N'[{table}]', N'U') IS NOT NULL "
                            f"DROP TABLE [{table}];\nGO\n")
                    f.write(self._create_table_ddl(cursor, table) + "\nGO\n\n")

                    has_identity = self._has_identity(cursor, table)
                    if has_identity:
                        f.write(f"SET IDENTITY_INSERT [{table}] ON;\nGO\n")

                    cursor.execute(f"SELECT * FROM [{table}]")
                    cols = [d[0] for d in cursor.description]
                    col_list = ", ".join(f"[{c}]" for c in cols)

                    while True:
                        rows = cursor.fetchmany(1000)
                        if not rows:
                            break
                        for row in rows:
                            vals = ", ".join(self._quote_value(v) for v in row)
                            f.write(
                                f"INSERT INTO [{table}] ({col_list}) VALUES ({vals});\n"
                            )

                    if has_identity:
                        f.write(f"SET IDENTITY_INSERT [{table}] OFF;\nGO\n")
                    f.write("\n")

        finally:
            cursor.close()
            conn.close()

        return backup_path

    def restore_from_backup(self, backup_path: str) -> None:
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        conn = self._connect()
        cursor = conn.cursor()
        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Split on GO statements (T-SQL batch separator)
            batches = [b.strip() for b in content.split("\nGO") if b.strip()]
            for batch in batches:
                if batch.startswith("--"):
                    continue
                try:
                    cursor.execute(batch)
                    conn.commit()
                except pyodbc.Error as e:
                    print(f"[MSSQLRestore] Batch failed (continuing): {e}")
        finally:
            cursor.close()
            conn.close()

    def test_connection(self) -> bool:
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
