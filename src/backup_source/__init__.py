from src.backup_source.elasticsearch import ElasticsearchBackupManager
from src.backup_source.postgres import PostgresBackupManager
from src.backup_source.qdrant import QdrantBackupManager
from src.backup_source.vault import VaultBackupManager
from typing import Literal
from src.base import Credentials, BaseBackupManager


class BackupManager:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials

    def create_from_type(
        self, source_type: Literal["vault", "qdrant", "postgres", "elasticsearch"]
    ) -> BaseBackupManager:
        map_ = {
            "vault": VaultBackupManager,
            "qdrant": QdrantBackupManager,
            "postgres": PostgresBackupManager,
            "elasticsearch": ElasticsearchBackupManager,
        }

        return map_[source_type](self.credentials)
