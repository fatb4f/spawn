"""Canonical schema models for spawn contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Event taxonomy (spec-first). Keep this list additive for compatibility.
EVENT_TYPES = (
    "codex.session.started",
    "codex.session.updated",
    "codex.session.ended",
    "codex.session.stalled",
    "codex.config.changed",
    "codex.session.meta.refresh.failed",
    "codex.session.meta.prompt.changed",
    "codex.session.resume.failed",
    "codex.session.service.restarted",
    "spawn.alert.raised",
)

EventType = Literal[
    "codex.session.started",
    "codex.session.updated",
    "codex.session.ended",
    "codex.session.stalled",
    "codex.config.changed",
    "codex.session.meta.refresh.failed",
    "codex.session.meta.prompt.changed",
    "codex.session.resume.failed",
    "codex.session.service.restarted",
    "spawn.alert.raised",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class EventEnvelopeV1(ContractModel):
    schema_name: Literal["event_envelope_v1"] = Field(
        default="event_envelope_v1",
        alias="schema",
        serialization_alias="schema",
    )
    event_id: str
    event_type: EventType
    source: str
    observed_at: str
    dedupe_key: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionPolicyV1(ContractModel):
    timeout_sec: int = 30
    retry: str = "none"
    execution_class: str = "transient"


class ActionRequestV1(ContractModel):
    schema_name: Literal["action_request_v1"] = Field(
        default="action_request_v1",
        alias="schema",
        serialization_alias="schema",
    )
    request_id: str
    event_id: str
    action: str
    policy: ActionPolicyV1
    args: list[str] = Field(default_factory=list)


class ActionArtifactsV1(ContractModel):
    stdout: str = ""
    stderr: str = ""


class ActionResultV1(ContractModel):
    schema_name: Literal["action_result_v1"] = Field(
        default="action_result_v1",
        alias="schema",
        serialization_alias="schema",
    )
    request_id: str
    event_id: str
    action: str
    status: str
    return_code: int
    started_at: str
    finished_at: str
    artifacts: ActionArtifactsV1
