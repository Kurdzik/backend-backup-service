import base64
import json
import os
import uuid
from datetime import date, datetime, time
from typing import Any, Optional
from urllib.parse import urlparse

from neo4j import GraphDatabase, basic_auth, bearer_auth
from neo4j.time import Date as Neo4jDate
from neo4j.time import DateTime as Neo4jDateTime
from neo4j.time import Duration
from neo4j.time import Time as Neo4jTime

from src.base import BaseBackupManager, Credentials
from src.logger import get_logger

logger = get_logger()


class Neo4jBackupManager(BaseBackupManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.uri = self._normalize_uri(credentials.url)
        self.database = self._parse_database(credentials.url)
        self.driver = GraphDatabase.driver(self.uri, auth=self._get_auth())

    def _normalize_uri(self, url: str) -> str:
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            return f"bolt://{url}"

        return url

    def _parse_database(self, url: str) -> Optional[str]:
        parsed_url = urlparse(url)
        database = parsed_url.path.strip("/")
        return database or None

    def _get_auth(self):
        if self.credentials.api_key:
            return bearer_auth(self.credentials.api_key)
        if self.credentials.login and self.credentials.password:
            return basic_auth(self.credentials.login, self.credentials.password)
        return None

    def _session_kwargs(self) -> dict[str, str]:
        if self.database:
            return {"database": self.database}
        return {}

    @staticmethod
    def _escape_identifier(identifier: str) -> str:
        return f"`{identifier.replace('`', '``')}`"

    def _run_optional_schema_query(self, query: str) -> list[str]:
        try:
            with self.driver.session(**self._session_kwargs()) as session:
                result = session.run(query)
                return [record["createStatement"] for record in result if record["createStatement"]]
        except Exception as e:
            logger.warning("neo4j_schema_query_failed", query=query, error=str(e))
            return []

    def _collect_schema(self) -> dict[str, list[str]]:
        constraints = self._run_optional_schema_query(
            "SHOW CONSTRAINTS YIELD createStatement "
            "WHERE createStatement IS NOT NULL "
            "RETURN createStatement ORDER BY createStatement"
        )
        indexes = self._run_optional_schema_query(
            "SHOW INDEXES YIELD createStatement, owningConstraint, type "
            "WHERE createStatement IS NOT NULL AND owningConstraint IS NULL "
            "AND type <> 'LOOKUP' RETURN createStatement ORDER BY createStatement"
        )

        return {"constraints": constraints, "indexes": indexes}

    def _serialize_value(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, bytes):
            return {
                "__neo4j_type__": "bytes",
                "value": base64.b64encode(value).decode("ascii"),
            }
        if isinstance(value, Neo4jDateTime):
            return {"__neo4j_type__": "neo4j_datetime", "value": value.iso_format()}
        if isinstance(value, Neo4jDate):
            return {"__neo4j_type__": "neo4j_date", "value": value.iso_format()}
        if isinstance(value, Neo4jTime):
            return {"__neo4j_type__": "neo4j_time", "value": value.iso_format()}
        if isinstance(value, datetime):
            return {"__neo4j_type__": "datetime", "value": value.isoformat()}
        if isinstance(value, date):
            return {"__neo4j_type__": "date", "value": value.isoformat()}
        if isinstance(value, time):
            return {"__neo4j_type__": "time", "value": value.isoformat()}
        if isinstance(value, Duration):
            return {
                "__neo4j_type__": "duration",
                "months": value.months,
                "days": value.days,
                "seconds": value.seconds,
                "nanoseconds": value.nanoseconds,
            }
        if isinstance(value, (list, tuple)):
            return [self._serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialize_value(item) for key, item in value.items()}

        if hasattr(value, "iso_format"):
            return {
                "__neo4j_type__": value.__class__.__name__.lower(),
                "value": value.iso_format(),
            }

        raise TypeError(f"Unsupported Neo4j property type: {type(value).__name__}")

    def _deserialize_value(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._deserialize_value(item) for item in value]
        if not isinstance(value, dict):
            return value

        value_type = value.get("__neo4j_type__")
        if not value_type:
            return {key: self._deserialize_value(item) for key, item in value.items()}

        if value_type == "bytes":
            return base64.b64decode(value["value"])
        if value_type == "neo4j_datetime":
            return Neo4jDateTime.from_iso_format(value["value"])
        if value_type == "neo4j_date":
            return Neo4jDate.from_iso_format(value["value"])
        if value_type == "neo4j_time":
            return Neo4jTime.from_iso_format(value["value"])
        if value_type == "datetime":
            return datetime.fromisoformat(value["value"])
        if value_type == "date":
            return date.fromisoformat(value["value"])
        if value_type == "time":
            return time.fromisoformat(value["value"])
        if value_type == "duration":
            return Duration(
                months=value["months"],
                days=value["days"],
                seconds=value["seconds"],
                nanoseconds=value["nanoseconds"],
            )

        return value["value"]

    def _serialize_properties(self, properties: dict[str, Any]) -> dict[str, Any]:
        return {key: self._serialize_value(value) for key, value in properties.items()}

    def _deserialize_properties(self, properties: dict[str, Any]) -> dict[str, Any]:
        return {key: self._deserialize_value(value) for key, value in properties.items()}

    def create_backup(
        self, tenant_id: str, backup_source_id: int, schedule_id: Optional[int] = None
    ) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"neo4j_backup_usr={tenant_id}_sch={schedule_id}_src={backup_source_id}_created_at={timestamp}.json"

        schema = self._collect_schema()
        payload = {
            "schema_version": 1,
            "database": self.database,
            "constraints": schema["constraints"],
            "indexes": schema["indexes"],
            "nodes": [],
            "relationships": [],
        }

        with self.driver.session(**self._session_kwargs()) as session:
            nodes = session.run(
                "MATCH (n) RETURN elementId(n) AS element_id, labels(n) AS labels, properties(n) AS properties"
            )
            for record in nodes:
                payload["nodes"].append(
                    {
                        "element_id": record["element_id"],
                        "labels": record["labels"],
                        "properties": self._serialize_properties(record["properties"]),
                    }
                )

            relationships = session.run(
                "MATCH (start)-[r]->(end) "
                "RETURN elementId(r) AS element_id, elementId(start) AS start_id, "
                "elementId(end) AS end_id, type(r) AS type, properties(r) AS properties"
            )
            for record in relationships:
                payload["relationships"].append(
                    {
                        "element_id": record["element_id"],
                        "start_id": record["start_id"],
                        "end_id": record["end_id"],
                        "type": record["type"],
                        "properties": self._serialize_properties(record["properties"]),
                    }
                )

        with open(backup_path, "w", encoding="utf-8") as backup_file:
            json.dump(payload, backup_file, separators=(",", ":"))

        if not os.path.exists(backup_path):
            raise RuntimeError(f"Backup file was not created: {backup_path}")

        return backup_path

    def _clear_database(self, session) -> None:
        session.run("MATCH ()-[r]->() DELETE r").consume()
        session.run("MATCH (n) DELETE n").consume()

        try:
            constraints = session.run("SHOW CONSTRAINTS YIELD name RETURN name")
            for record in constraints:
                session.run(
                    f"DROP CONSTRAINT {self._escape_identifier(record['name'])} IF EXISTS"
                ).consume()
        except Exception as e:
            logger.warning("neo4j_drop_constraints_failed", error=str(e))

        try:
            indexes = session.run(
                "SHOW INDEXES YIELD name, type, owningConstraint "
                "WHERE owningConstraint IS NULL AND type <> 'LOOKUP' RETURN name"
            )
            for record in indexes:
                session.run(
                    f"DROP INDEX {self._escape_identifier(record['name'])} IF EXISTS"
                ).consume()
        except Exception as e:
            logger.warning("neo4j_drop_indexes_failed", error=str(e))

    def _create_node(self, session, node: dict[str, Any], restore_id_property: str) -> None:
        labels = ":".join(self._escape_identifier(label) for label in node["labels"])
        restore_id = node["element_id"]
        properties = self._deserialize_properties(node["properties"])
        query = (
            f"CREATE (n{':' + labels if labels else ''}) "
            "SET n = $properties "
            f"SET n.{self._escape_identifier(restore_id_property)} = $restore_id"
        )
        session.run(query, properties=properties, restore_id=restore_id).consume()

    def _create_relationship(
        self, session, relationship: dict[str, Any], restore_id_property: str
    ) -> None:
        relationship_type = self._escape_identifier(relationship["type"])
        restore_id_identifier = self._escape_identifier(restore_id_property)
        query = (
            f"MATCH (start {{{restore_id_identifier}: $start_id}}), "
            f"(end {{{restore_id_identifier}: $end_id}}) "
            f"CREATE (start)-[r:{relationship_type}]->(end) "
            "SET r = $properties"
        )
        session.run(
            query,
            start_id=relationship["start_id"],
            end_id=relationship["end_id"],
            properties=self._deserialize_properties(relationship["properties"]),
        ).consume()

    def restore_from_backup(self, backup_path: str) -> None:
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        with open(backup_path, "r", encoding="utf-8") as backup_file:
            payload = json.load(backup_file)

        restore_id_property = f"_backup_restore_id_{uuid.uuid4().hex}"

        with self.driver.session(**self._session_kwargs()) as session:
            self._clear_database(session)

            for node in payload.get("nodes", []):
                self._create_node(session, node, restore_id_property)

            for relationship in payload.get("relationships", []):
                self._create_relationship(session, relationship, restore_id_property)

            session.run(
                f"MATCH (n) REMOVE n.{self._escape_identifier(restore_id_property)}"
            ).consume()

            for statement in payload.get("constraints", []):
                session.run(statement).consume()

            for statement in payload.get("indexes", []):
                session.run(statement).consume()

    def test_connection(self) -> bool:
        try:
            self.driver.verify_connectivity()
            with self.driver.session(**self._session_kwargs()) as session:
                session.run("RETURN 1").consume()
            return True
        except Exception as e:
            logger.info("neo4j_connection_test_failed", error=str(e))
            return False
