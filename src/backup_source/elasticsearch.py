import json
import os
from datetime import datetime
from typing import Optional

import httpx

from src.base import BaseBackupManager, Credentials

from elasticsearch import Elasticsearch
import tarfile
import json
import os
import tempfile
from datetime import datetime


class ElasticsearchBackupManager(BaseBackupManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.client = Elasticsearch([credentials.url])
        if credentials.api_key:
            self.client = Elasticsearch([credentials.url], api_key=credentials.api_key)
        elif credentials.login and credentials.password:
            self.client = Elasticsearch(
                [credentials.url], basic_auth=(credentials.login, credentials.password)
            )

    def create_backup(self) -> str:
        """Create backup of all Elasticsearch indexes

        Returns:
            str: Path to the locally created backup tar.gz file
        """
        temp_dir = tempfile.mkdtemp()

        try:
            # Get all indices
            indices = self.client.indices.get(index="*")

            if not indices:
                raise ValueError("No indices found in Elasticsearch cluster")

            # Backup each index
            for index_name in indices.keys():
                index_data = {
                    "settings": self.client.indices.get_settings(index=index_name),
                    "mappings": self.client.indices.get_mapping(index=index_name),
                    "documents": [],
                }

                # Scroll through all documents in the index
                resp = self.client.search(
                    index=index_name,
                    scroll="2m",
                    size=1000,
                    body={"query": {"match_all": {}}},
                )

                while resp["hits"]["hits"]:
                    for hit in resp["hits"]["hits"]:
                        index_data["documents"].append(hit["_source"])

                    scroll_id = resp.get("_scroll_id")
                    resp = self.client.scroll(scroll_id=scroll_id, scroll="2m")

                # Write index data to JSON file
                index_file = os.path.join(temp_dir, f"{index_name}.json")
                with open(index_file, "w") as f:
                    json.dump(index_data, f, indent=2, default=str)

            # Create tar.gz archive
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"elasticsearch_backup_{timestamp}.tar.gz"

            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(temp_dir, arcname="elasticsearch_backup")

            return backup_path

        finally:
            # Cleanup temporary directory
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)

    def restore_from_backup(self, backup_path: str, backup_destination: str) -> None:
        """Restore Elasticsearch indexes from backup

        Args:
            backup_path: Path to the backup tar.gz file
            backup_destination: Elasticsearch cluster URL to restore to (optional, uses current client if not provided)
        """
        temp_dir = tempfile.mkdtemp()

        try:
            # Extract tar.gz archive
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(temp_dir)

            backup_dir = os.path.join(temp_dir, "elasticsearch_backup")

            # Restore each index
            for json_file in os.listdir(backup_dir):
                if not json_file.endswith(".json"):
                    continue

                index_name = json_file.replace(".json", "")

                with open(os.path.join(backup_dir, json_file), "r") as f:
                    index_data = json.load(f)

                # Delete index if it exists
                try:
                    self.client.indices.delete(index=index_name)
                except Exception:
                    pass

                # Create index with settings
                settings = index_data.get("settings", {})
                mappings = index_data.get("mappings", {})

                self.client.indices.create(
                    index=index_name,
                    settings=settings.get(index_name, {}).get("settings", {}),
                    mappings=mappings.get(index_name, {}).get("mappings", {}),
                )

                # Restore documents
                documents = index_data.get("documents", [])
                for doc in documents:
                    self.client.index(index=index_name, document=doc)

        finally:
            # Cleanup temporary directory
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir_name in dirs:
                    os.rmdir(os.path.join(root, dir_name))
            os.rmdir(temp_dir)

    def test_connection(self) -> bool:
        """Test whether the Elasticsearch cluster is reachable
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            # Attempt to get cluster info
            self.client.info()
            return True
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False