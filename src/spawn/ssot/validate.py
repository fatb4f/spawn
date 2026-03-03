"""Validation helpers for SSOT contracts."""

from __future__ import annotations

from typing import Any

from spawn.ssot.registry import schema_registry


def validate_payload(
    schema_name: str, payload: dict[str, Any], version: str = "v1"
) -> list[str]:
    return schema_registry.validate(name=schema_name, version=version, payload=payload)


def validate_or_raise(
    schema_name: str, payload: dict[str, Any], version: str = "v1"
) -> None:
    errors = validate_payload(schema_name=schema_name, payload=payload, version=version)
    if errors:
        joined = "; ".join(errors)
        raise ValueError(f"{schema_name}:{version} validation failed: {joined}")
