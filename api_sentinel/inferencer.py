"""
API Sentinel - Schema Inferencer
Generates and normalizes JSON Schemas from runtime payloads using genson.
"""

from typing import Any, Dict
from genson import SchemaBuilder


class SchemaInferencer:
    """Infers JSON Schema from raw request/response payload objects."""

    def __init__(self, schema_uri: str | None = None):
        self.schema_uri = schema_uri

    def infer_schema(self, data: Any) -> Dict[str, Any]:
        """
        Infer a JSON Schema from Python data structures (dict, list, etc.).
        """
        if data is None:
            return {"type": "null"}

        builder = SchemaBuilder(schema_uri=self.schema_uri)
        builder.add_object(data)
        schema = builder.to_schema()
        return self.normalize_schema(schema)

    @staticmethod
    def normalize_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean up and normalize inferred schema for OpenAPI comparison.
        Strips meta attributes like $schema if present.
        """
        normalized = dict(schema)
        normalized.pop("$schema", None)
        return normalized
