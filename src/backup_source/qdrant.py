import json
import os
from datetime import datetime
from typing import Dict, Optional

import httpx

from src.base import BaseBackupManager, Credentials
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import json
import tarfile
import os
import tempfile
from datetime import datetime


class QdrantBackupManager(BaseBackupManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)

        if credentials.api_key:
            self.client = QdrantClient(url=credentials.url, api_key=credentials.api_key)
        elif credentials.login and credentials.password:
            self.client = QdrantClient(url=credentials.url, api_key=credentials.login)
        else:
            self.client = QdrantClient(url=credentials.url)

    def create_backup(self) -> str:
        """Create backup of all Qdrant collections

        Returns:
            str: Path to the locally created backup tar.gz file
        """
        temp_dir = tempfile.mkdtemp()

        try:
            # Get all collections
            collections = self.client.get_collections()

            if not collections.collections:
                raise ValueError("No collections found in Qdrant")

            # Backup each collection
            for collection in collections.collections:
                collection_name = collection.name
                collection_info = self.client.get_collection(collection_name)

                collection_data = {
                    "name": collection_name,
                    "config": {
                        "vectors": collection_info.config.params.vectors.to_dict()
                        if hasattr(collection_info.config.params.vectors, "to_dict")
                        else str(collection_info.config.params.vectors),
                        "shard_number": collection_info.config.params.shard_number,
                        "replication_factor": collection_info.config.params.replication_factor,
                    },
                    "points": [],
                }

                # Scroll through all points in the collection
                offset = 0
                limit = 1000

                while True:
                    points, next_page_offset = self.client.scroll(
                        collection_name=collection_name,
                        limit=limit,
                        offset=offset,
                        with_vectors=True,
                        with_payload=True,
                    )

                    if not points:
                        break

                    for point in points:
                        collection_data["points"].append(
                            {
                                "id": point.id,
                                "vector": point.vector,
                                "payload": point.payload,
                            }
                        )

                    offset = next_page_offset
                    if next_page_offset is None:
                        break

                # Write collection data to JSON file
                collection_file = os.path.join(temp_dir, f"{collection_name}.json")
                with open(collection_file, "w") as f:
                    json.dump(collection_data, f, indent=2, default=str)

            # Create tar.gz archive
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"qdrant_backup_{timestamp}.tar.gz"

            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(temp_dir, arcname="qdrant_backup")

            return backup_path

        finally:
            # Cleanup temporary directory
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)

    def restore_from_backup(self, backup_path: str, backup_destination: str) -> None:
        """Restore Qdrant collections from backup

        Args:
            backup_path: Path to the backup tar.gz file
            backup_destination: Qdrant instance URL to restore to (optional, uses current client if not provided)
        """
        temp_dir = tempfile.mkdtemp()

        try:
            # Extract tar.gz archive
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(temp_dir)

            backup_dir = os.path.join(temp_dir, "qdrant_backup")

            # Restore each collection
            for json_file in os.listdir(backup_dir):
                if not json_file.endswith(".json"):
                    continue

                with open(os.path.join(backup_dir, json_file), "r") as f:
                    collection_data = json.load(f)

                collection_name = collection_data["name"]
                config = collection_data["config"]
                points = collection_data["points"]

                # Delete collection if it exists
                try:
                    self.client.delete_collection(collection_name)
                except Exception:
                    pass

                # Create collection with config
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=config["vectors"]["size"], distance=Distance.COSINE
                    ),
                )

                # Restore points
                if points:
                    point_structs = []
                    for point in points:
                        point_structs.append(
                            PointStruct(
                                id=point["id"],
                                vector=point["vector"],
                                payload=point.get("payload", {}),
                            )
                        )

                    self.client.upsert(
                        collection_name=collection_name, points=point_structs
                    )

        finally:
            # Cleanup temporary directory
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir_name in dirs:
                    os.rmdir(os.path.join(root, dir_name))
            os.rmdir(temp_dir)

    def test_connection(self) -> bool:
        """Test whether the Qdrant instance is reachable
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            # Attempt to get collections to verify connectivity
            self.client.get_collections()
            return True
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False