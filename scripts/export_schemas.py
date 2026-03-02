#!/usr/bin/env python3
"""Export canonical JSON Schemas from pydantic contract models."""

from __future__ import annotations

import json
from pathlib import Path

from spawn.contracts.models import ActionRequestV1, ActionResultV1, EventEnvelopeV1
from spawn.contracts.tool_ssot import ComponentSpec, ContractSpec, DependencySpec, ToolSsotV1

OUT = Path("api/openapi/schemas")
SSOT_OUT = Path("api/openapi/tool_ssot.json")
MODELS = {
    "EventEnvelopeV1": EventEnvelopeV1,
    "ActionRequestV1": ActionRequestV1,
    "ActionResultV1": ActionResultV1,
    "ToolSsotV1": ToolSsotV1,
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        path = OUT / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(path)

    ssot = ToolSsotV1(
        version="0.1.0",
        components=[
            ComponentSpec(name="spawnd", role="daemon", entrypoint="spawn.core.service:main"),
            ComponentSpec(name="spawnctl", role="cli", entrypoint="spawn.cli:main"),
            ComponentSpec(name="contracts", role="schema", entrypoint="src/spawn/contracts/models.py"),
        ],
        dependencies=[
            DependencySpec(name="grpcio", kind="runtime"),
            DependencySpec(name="pydantic", kind="runtime"),
            DependencySpec(name="dataconfy", kind="runtime"),
            DependencySpec(name="xdg-base-dirs", kind="runtime"),
            DependencySpec(name="protobuf", kind="runtime"),
            DependencySpec(
                name="grpcio-tools",
                kind="build",
                required=False,
                note="Used only by scripts/gen.sh via uv --with",
            ),
        ],
        contracts=[
            ContractSpec(
                name="spawn_control",
                kind="proto",
                path="api/proto/spawn/v1/spawn_control.proto",
                lifecycle="canonical",
            ),
            ContractSpec(
                name="openapi_component_catalog",
                kind="openapi",
                path="api/openapi/openapi.yaml",
                lifecycle="derived",
            ),
            ContractSpec(
                name="runtime_contract_models",
                kind="pydantic_model",
                path="src/spawn/contracts/models.py",
                lifecycle="canonical",
            ),
            ContractSpec(
                name="tool_ssot",
                kind="json_schema",
                path="api/openapi/schemas/ToolSsotV1.schema.json",
                lifecycle="derived",
            ),
        ],
    )
    SSOT_OUT.parent.mkdir(parents=True, exist_ok=True)
    SSOT_OUT.write_text(json.dumps(ssot.model_dump(by_alias=True), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(SSOT_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
