from src.backup_source.elasticsearch import ElasticsearchBackupManager
from src.backup_source.postgres import PostgresBackupManager
from src.backup_source.qdrant import QdrantBackupManager
from src.backup_source.vault import VaultBackupManager
from typing import Literal
from src.base import Credentials


class BackupManager:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials

    def create_from_type(
        self, source_type: Literal["vault", "qdrant", "postgres", "elasticsearch"]
    ):
        map_ = {
            "vault": VaultBackupManager(self.credentials),
            "qdrant": QdrantBackupManager(self.credentials),
            "postgres": PostgresBackupManager(self.credentials),
            "elasticsearch": ElasticsearchBackupManager(self.credentials),
        }

        return map_[source_type]
