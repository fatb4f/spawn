#!/usr/bin/env python3
"""Derive OpenAPI spec from canonical contract schemas."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / "api" / "openapi" / "schemas"
OUT = ROOT / "api" / "openapi" / "openapi.yaml"
PROTO_CANONICAL = "api/proto/spawn/v1/spawn_control.proto"
MODEL_CANONICAL = "src/spawn/contracts/models.py"


def schema_name(path: Path) -> str:
    suffix = ".schema.json"
    if path.name.endswith(suffix):
        return path.name[: -len(suffix)]
    return path.stem


def main() -> int:
    schema_files = sorted(SCHEMAS_DIR.glob("*.schema.json"))
    if not schema_files:
        raise SystemExit("no schemas found; run scripts/export_schemas.py first")

    components = {
        schema_name(path): {"$ref": f"./schemas/{path.name}"}
        for path in schema_files
    }

    doc = {
        "openapi": "3.1.0",
        "info": {
            "title": "spawn control and event contracts",
            "version": "0.1.0",
            "description": "Derived OpenAPI component catalog for spawn contracts.",
        },
        "servers": [],
        "paths": {},
        "components": {"schemas": components},
        "x-derived-from": [MODEL_CANONICAL, PROTO_CANONICAL],
    }
    OUT.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
