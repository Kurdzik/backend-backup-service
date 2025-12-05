from src.backup_destination.local_fs import LocalFSBackupDestination
from src.backup_destination.s3 import S3BackupDestination
from src.backup_destination.sftp import SFTPBackupDestination
from typing import Literal
from src.base import Credentials


class BackupDestinationManager:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials

    def create_from_type(self, source_type: Literal["s3", "local_fs", "sftp"]):
        map_ = {
            "s3": LocalFSBackupDestination(self.credentials),
            "local_fs": S3BackupDestination(self.credentials),
            "sftp": SFTPBackupDestination(self.credentials),
        }

        return map_[source_type]
