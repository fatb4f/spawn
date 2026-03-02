"""Tool SSOT contract model."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SsotModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class DependencySpec(SsotModel):
    name: str
    kind: Literal["runtime", "build", "dev"]
    required: bool = True
    note: str = ""


class ContractSpec(SsotModel):
    name: str
    canonical_path: str
    kind: Literal["proto", "openapi", "json_schema", "pydantic_model"]


class ComponentSpec(SsotModel):
    name: str
    role: Literal["daemon", "cli", "adapter", "core", "schema", "generated"]
    entrypoint: str = ""


class ToolSsotV1(SsotModel):
    schema_name: Literal["tool_ssot_v1"] = Field(
        default="tool_ssot_v1",
        alias="schema",
        serialization_alias="schema",
    )
    tool: Literal["spawn"] = "spawn"
    version: str = "0.1.0"
    components: list[ComponentSpec] = Field(default_factory=list)
    dependencies: list[DependencySpec] = Field(default_factory=list)
    contracts: list[ContractSpec] = Field(default_factory=list)
