import json
import os
import tarfile
import tempfile
from datetime import datetime
from typing import Dict, Optional

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.base import BaseBackupManager, Credentials


class QdrantBackupManager(BaseBackupManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)

        if credentials.api_key:
            self.client = QdrantClient(
                url=credentials.url, api_key=credentials.api_key, timeout=36000
            )
        elif credentials.login and credentials.password:
            self.client = QdrantClient(
                url=credentials.url, api_key=credentials.login, timeout=36000
            )
        else:
            self.client = QdrantClient(url=credentials.url, timeout=36000)

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

    def create_backup(self, backup_source_id: int) -> str:
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

                # Properly serialize vector config
                vectors_config = collection_info.config.params.vectors
                if hasattr(vectors_config, "model_dump"):
                    vectors_dict = vectors_config.model_dump()  # ty:ignore[call-non-callable]
                elif hasattr(vectors_config, "dict"):
                    vectors_dict = vectors_config.dict()  # ty:ignore[call-non-callable]
                else:
                    # Fallback: extract key attributes
                    vectors_dict = {
                        "size": vectors_config.size,  # ty:ignore[possibly-missing-attribute]
                        "distance": str(vectors_config.distance),  # ty:ignore[possibly-missing-attribute]
                    }

                collection_data = {
                    "name": collection_name,
                    "config": {
                        "vectors": vectors_dict,
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
                        collection_data["points"].append(  # ty:ignore[possibly-missing-attribute]
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
            backup_path = f"qdrant_backup_{backup_source_id}_{timestamp}.tar.gz"

            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(temp_dir, arcname="qdrant_backup")

            return backup_path

        finally:
            # Cleanup temporary directory
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)

    def restore_from_backup(self, backup_path: str) -> None:
        """Restore Qdrant collections from backup

        Args:
            backup_path: Path to the backup tar.gz file
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

                # Reconstruct vector config
                vectors_config_data = config["vectors"]

                # Extract size and distance from the saved config
                size = vectors_config_data.get("size")
                distance_str = vectors_config_data.get("distance", "Cosine")

                # Parse distance enum
                if isinstance(distance_str, str):
                    distance_str = distance_str.split(".")[
                        -1
                    ]  # Handle "Distance.COSINE" format
                    distance = (
                        Distance[distance_str.upper()]
                        if distance_str
                        else Distance.COSINE
                    )
                else:
                    distance = distance_str

                # Create collection with config
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=size, distance=distance),
                )

                # Restore points in batches
                if points:
                    batch_size = 500  # Adjust if needed
                    for i in range(0, len(points), batch_size):
                        batch = points[i : i + batch_size]
                        point_structs = []
                        for point in batch:
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
                        print(
                            f"Restored {min(i + batch_size, len(points))}/{len(points)} points for {collection_name}"
                        )

        finally:
            # Cleanup temporary directory
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir_name in dirs:
                    os.rmdir(os.path.join(root, dir_name))
            os.rmdir(temp_dir)
