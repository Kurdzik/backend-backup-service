from src.backup_destination.local_fs import LocalFSBackupDestination
from src.backup_destination.s3 import S3BackupDestination
from src.backup_destination.sftp import SFTPBackupDestination
from src.base import BaseBackupDestinationManager, Credentials


class BackupDestinationManager:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials

    def create_from_type(self, source_type: str) -> BaseBackupDestinationManager:
        map_ = {
            "s3": S3BackupDestination,
            "local_fs": LocalFSBackupDestination,
            "sftp": SFTPBackupDestination,
        }

        return map_[source_type](self.credentials)
