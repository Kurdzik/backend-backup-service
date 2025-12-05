import inspect
from typing import Optional
import os
from pydantic import BaseModel
import uuid

class Credentials(BaseModel):
    url: str
    login: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None

class BackupDetails(BaseModel):
    name: str
    path: str
    size: float
    modified: str


class BaseBackupManager:
    def __init__(self, credentials: Credentials) -> None:
        self.credentials = credentials

    def create_backup(self) -> str:
        """Create backup from source using provided credentials
        
        Returns:
            str: Path to the locally created backup file
        """
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented" # type: ignore
        )

    def restore_from_backup(self, backup_path: str, backup_destination: str) -> None:
        """Restore source using provided credentials
        
        Args:
            backup_path: Path to the backup file to restore from
            backup_destination: Destination where the backup should be restored to
        """
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented" # type: ignore
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
            f"Method {inspect.currentframe().f_code.co_name} is not implemented" # type: ignore
        )

    def list_backups(self) -> list[BackupDetails]:
        """List all backups stored in a specified destination
        
        Returns:
            list[BackupDetails]: List of backup details stored at the destination
        """
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented" # type: ignore
        )

    def delete_backup(self, backup_path: str) -> None:
        """Delete specified backup from a specified destination
        
        Args:
            backup_path: Path/identifier of the backup to delete
        """
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented" # type: ignore
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
            f"Method {inspect.currentframe().f_code.co_name} is not implemented" # type: ignore
        )

    def _delete_extra_backups(self, keep_n: int = 5) -> None:
        """Delete extra backups from destination, keeping only the most recent N backups
        
        Args:
            keep_n: Number of backups to keep (default: 5)
        """
        raise NotImplementedError(
            f"Method {inspect.currentframe().f_code.co_name} is not implemented" # type: ignore
        )


def create_backup(
    backup_manager: BaseBackupManager,
    backup_destination_manager: BaseBackupDestinationManager
) -> str:
    """Create a backup and upload it to the destination
    
    Args:
        backup_manager: Manager responsible for creating the backup
        backup_destination_manager: Manager responsible for uploading to destination
        
    Returns:
        str: Remote path/identifier of the uploaded backup
    """
    local_path = backup_manager.create_backup()
    
    try:
        remote_path = backup_destination_manager.upload_backup(local_path)
        return remote_path
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)


def list_backups(backup_destination_manager: BaseBackupDestinationManager) -> list[BackupDetails]:
    """List all available backups at the destination
    
    Args:
        backup_destination_manager: Manager responsible for listing backups
        
    Returns:
        list[BackupDetails]: List of backup details
    """
    return backup_destination_manager.list_backups()


def restore_from_backup(
    backup_path: str,
    backup_manager: BaseBackupManager,
    backup_destination_manager: BaseBackupDestinationManager,
    backup_destination: str
) -> None:
    """Restore a backup from the destination to the source
    
    Args:
        backup_path: Remote path/identifier of the backup to restore
        backup_manager: Manager responsible for restoring the backup
        backup_destination_manager: Manager responsible for downloading from destination
        backup_destination: Destination where the backup should be restored to
    """
    local_path = backup_destination_manager.get_backup(backup_path)
    
    try:
        backup_manager.restore_from_backup(local_path, backup_destination)
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)