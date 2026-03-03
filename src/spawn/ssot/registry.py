"""Schema registry for spawn SSOT contracts."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag

from jsonschema import Draft202012Validator, SchemaError
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
        self._resource_docs: dict[str, dict[str, Any]] = {}
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
            self._resource_docs[uri] = schema
            self._resource_docs[file_name] = schema
            self._resource_docs[f"./{file_name}"] = schema
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

    def validate_tree(self) -> list[str]:
        errors: list[str] = []
        for key, schema in sorted(self._schemas.items()):
            descriptor = self._descriptors[key]
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as exc:
                errors.append(f"{descriptor.file}: invalid schema: {exc.message}")
                continue

            for ref in sorted(self._collect_refs(schema)):
                target_schema, fragment = self._resolve_ref(schema, descriptor.file, ref)
                if target_schema is None:
                    errors.append(f"{descriptor.file}: unresolved $ref '{ref}'")
                    continue
                if not self._fragment_exists(target_schema, fragment):
                    errors.append(f"{descriptor.file}: unresolved fragment '{ref}'")
        return sorted(set(errors))

    def _collect_refs(self, node: Any) -> set[str]:
        refs: set[str] = set()
        if isinstance(node, dict):
            ref_value = node.get("$ref")
            if isinstance(ref_value, str):
                refs.add(ref_value)
            for value in node.values():
                refs.update(self._collect_refs(value))
        elif isinstance(node, list):
            for item in node:
                refs.update(self._collect_refs(item))
        return refs

    def _resolve_ref(self, current_schema: dict[str, Any], current_file: str, ref: str) -> tuple[dict[str, Any] | None, str]:
        base, fragment = urldefrag(ref)
        if not base:
            return current_schema, fragment

        if base in self._resource_docs:
            return self._resource_docs[base], fragment
        if base.startswith("./") and base[2:] in self._resource_docs:
            return self._resource_docs[base[2:]], fragment
        if not base.startswith("./"):
            rel = f"./{base}"
            if rel in self._resource_docs:
                return self._resource_docs[rel], fragment

        # Resolve file-local relative paths from current file directory.
        current_dir = str(Path(current_file).parent).replace("\\", "/")
        if current_dir and current_dir != ".":
            candidate = f"{current_dir}/{base}"
            if candidate in self._resource_docs:
                return self._resource_docs[candidate], fragment
            if f"./{candidate}" in self._resource_docs:
                return self._resource_docs[f"./{candidate}"], fragment
        return None, fragment

    def _fragment_exists(self, schema: dict[str, Any], fragment: str) -> bool:
        if fragment == "":
            return True
        if fragment.startswith("/"):
            return self._pointer_exists(schema, fragment)
        return self._anchor_exists(schema, fragment)

    def _pointer_exists(self, doc: Any, pointer: str) -> bool:
        current = doc
        for token in pointer.lstrip("/").split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict):
                if token not in current:
                    return False
                current = current[token]
                continue
            if isinstance(current, list):
                if not token.isdigit():
                    return False
                idx = int(token)
                if idx < 0 or idx >= len(current):
                    return False
                current = current[idx]
                continue
            return False
        return True

    def _anchor_exists(self, doc: Any, anchor: str) -> bool:
        if isinstance(doc, dict):
            if doc.get("$anchor") == anchor:
                return True
            return any(self._anchor_exists(value, anchor) for value in doc.values())
        if isinstance(doc, list):
            return any(self._anchor_exists(item, anchor) for item in doc)
        return False


schema_registry = SchemaRegistry()
