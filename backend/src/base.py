import inspect
import os
import uuid
from typing import Optional
import re
from pydantic import BaseModel
from src.models.structs import Credentials, BackupDetails





class BaseBackupManager:
    def __init__(self, credentials: Credentials) -> None:
        self.credentials = credentials

    def create_backup(self, tenant_id: str, backup_source_id: int, schedule_id: Optional[int] = None) -> str:
        """Create backup from source using provided credentials

        Returns:
            str: Path to the locally created backup file
        """
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented"  # type: ignore
        )

    def restore_from_backup(self, backup_path: str) -> None:
        """Restore source using provided credentials

        Args:
            backup_path: Path to the backup file to restore from
            backup_destination: Destination where the backup should be restored to
        """
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented"  # type: ignore
        )

    def test_connection(self) -> bool:
        """Tests wheather the destination is reachable"""
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented"  # type: ignore
        )
    

class BaseBackupDestinationManager:
    def __init__(self, credentials: Credentials) -> None:
        self.credentials = credentials

    def upload_backup(self, local_backup_path: str) -> str:
        """Upload backup to a specified destination

        Args:
            local_backup_path: Path to the local backup file to upload

        Returns:
            str: Remote path/identifier of the uploaded backup
        """
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented"  # type: ignore
        )

    def list_backups(self) -> list[BackupDetails]:
        """List all backups stored in a specified destination

        Returns:
            list[BackupDetails]: List of backup details stored at the destination
        """
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented"  # type: ignore
        )

    def delete_backup(self, backup_path: str) -> None:
        """Delete specified backup from a specified destination

        Args:
            backup_path: Path/identifier of the backup to delete
        """
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented"  # type: ignore
        )

    def get_backup(self, backup_path: str, local_path: Optional[str] = None) -> str:
        """Download/retrieve specified backup from destination to local path

        Args:
            backup_path: Remote path/identifier of the backup to retrieve
            local_path: Optional local path where backup should be saved.
                       If not provided, a random path will be generated.

        Returns:
            str: Path to the downloaded backup file
        """
        if not local_path:
            local_path = str(uuid.uuid4()).replace("-", "")

        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented"  # type: ignore
        )

    def _delete_extra_backups(self, keep_n: int = 5) -> None:
        """Delete extra backups from destination, keeping only the most recent N backups

        Args:
            keep_n: Number of backups to keep (default: 5)
        """
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented"  # type: ignore
        )

    def test_connection(self) -> bool:
        """Tests wheather the destination is reachable"""
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented"  # type: ignore
        )
    
    @staticmethod
    def _parse_filename(filename: str):
        """Parse backup filename and extract info"""
        filename = os.path.basename(filename)

        pattern = r'^(\w+)_backup_usr=([a-f0-9\-]+)_sch=(\d+|None)_src=(\d+)_created_at=(\d+_\d+)\.(.+)$'
        
        match = re.match(pattern, filename)
        
        if not match:
            raise ValueError(f"Invalid backup filename format: {filename}")
        
        source, tenant_id, schedule_id, source_id, timestamp, extension = match.groups()
        
        return {
            'source': source,
            'tenant_id': tenant_id,
            'schedule_id': schedule_id,
            'source_id': source_id,
            'timestamp': timestamp,
            'extension': extension
        }