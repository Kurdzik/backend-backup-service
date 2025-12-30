import json
import os
import tarfile
import tempfile
from datetime import datetime
from typing import Optional

import httpx
from elasticsearch import Elasticsearch

from src.base import BaseBackupManager, Credentials


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

    def create_backup(
        self, tenant_id: str, backup_source_id: int, schedule_id: Optional[int] = None
    ) -> str:
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
            # Naming: <source-name>_backup_<source-id>_<timestamp>
            backup_path = f"elasticsearch_backup_usr={tenant_id}_sch={schedule_id}_src={backup_source_id}_created_at={timestamp}.tar.gz"

            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(temp_dir, arcname="elasticsearch_backup")

            return backup_path

        finally:
            # Cleanup temporary directory
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
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

    def restore_from_backup(self, backup_path: str) -> None:
        """Restore Elasticsearch indexes from backup

        Args:
            backup_path: Path to the backup tar.gz file
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

                # Extract settings and mappings with proper structure handling
                settings_wrapper = index_data.get("settings", {})
                mappings_wrapper = index_data.get("mappings", {})

                # Unwrap the index-specific nesting from Elasticsearch API response
                index_settings = (
                    settings_wrapper.get(index_name, {}).get("settings", {})
                    if isinstance(settings_wrapper, dict)
                    else {}
                )
                index_mappings = (
                    mappings_wrapper.get(index_name, {}).get("mappings", {})
                    if isinstance(mappings_wrapper, dict)
                    else {}
                )

                # Create index with settings and mappings
                try:
                    self.client.indices.create(
                        index=index_name,
                        settings=index_settings if index_settings else None,
                        mappings=index_mappings if index_mappings else None,
                    )
                except Exception as e:
                    # If index creation fails, try without settings/mappings
                    print(
                        f"Failed to create index {index_name} with settings/mappings: {e}"
                    )
                    self.client.indices.create(index=index_name)

                # Restore documents using bulk API with batching
                documents = index_data.get("documents", [])
                if documents:
                    batch_size = 1000
                    for i in range(0, len(documents), batch_size):
                        batch = documents[i : i + batch_size]
                        bulk_body = []
                        for doc in batch:
                            bulk_body.append({"index": {"_index": index_name}})
                            bulk_body.append(doc)

                        self.client.bulk(body=bulk_body)

        finally:
            # Cleanup temporary directory
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir_name in dirs:
                    os.rmdir(os.path.join(root, dir_name))
            os.rmdir(temp_dir)
