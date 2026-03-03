"""Schema registry for spawn SSOT contracts."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


@dataclass(frozen=True)
class SchemaDescriptor:
    name: str
    version: str
    file: str
    canonical: bool


class SchemaRegistry:
    """Loads and validates schemas from src/spawn/ssot/schemas."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or self._default_root()
        self.index_path = self.root / "schema.index.json"
        self._schemas: dict[str, dict[str, Any]] = {}
        self._descriptors: dict[str, SchemaDescriptor] = {}
        self._registry = Registry()
        self._load()

    def _default_root(self) -> Path:
        env = os.environ.get("SPAWN_SSOT_SCHEMA_ROOT", "").strip()
        if env:
            return Path(env).expanduser()
        return Path(__file__).resolve().parent / "schemas"

    def _load(self) -> None:
        if not self.index_path.exists():
            raise FileNotFoundError(f"schema index not found: {self.index_path}")
        raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        schemas = raw.get("schemas")
        if not isinstance(schemas, list):
            raise ValueError("schema.index.json: 'schemas' must be a list")

        registry = Registry()
        for item in schemas:
            if not isinstance(item, dict):
                raise ValueError("schema.index.json: schema entry must be an object")
            name = str(item.get("name", "")).strip()
            version = str(item.get("version", "")).strip()
            file_name = str(item.get("file", "")).strip()
            canonical = bool(item.get("canonical", False))
            if not name or not version or not file_name:
                raise ValueError("schema.index.json: each entry requires name/version/file")
            path = self.root / file_name
            if not path.exists():
                raise FileNotFoundError(f"schema file missing: {path}")
            schema = json.loads(path.read_text(encoding="utf-8"))
            key = f"{name}:{version}"
            self._schemas[key] = schema
            self._descriptors[key] = SchemaDescriptor(
                name=name,
                version=version,
                file=file_name,
                canonical=canonical,
            )
            uri = str(schema.get("$id", file_name))
            resource = Resource.from_contents(schema)
            registry = registry.with_resource(uri, resource)
            registry = registry.with_resource(file_name, resource)
            registry = registry.with_resource(f"./{file_name}", resource)
        self._registry = registry

    def list_schemas(self) -> list[SchemaDescriptor]:
        return [self._descriptors[k] for k in sorted(self._descriptors.keys())]

    def schema(self, name: str, version: str = "v1") -> dict[str, Any]:
        key = f"{name}:{version}"
        schema = self._schemas.get(key)
        if schema is None:
            available = ", ".join(sorted(self._schemas.keys()))
            raise KeyError(f"unknown schema '{key}' (available: {available})")
        return schema

    def validate(self, name: str, payload: dict[str, Any], version: str = "v1") -> list[str]:
        schema = self.schema(name=name, version=version)
        validator = Draft202012Validator(schema, registry=self._registry)
        errors = []
        for err in validator.iter_errors(payload):
            path = ".".join(str(part) for part in err.absolute_path)
            loc = path if path else "$"
            errors.append(f"{loc}: {err.message}")
        errors.sort()
        return errors


schema_registry = SchemaRegistry()
