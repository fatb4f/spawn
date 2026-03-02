"""Spawn contract helpers for event/action envelopes."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from spawn.contracts.models import ActionRequestV1, ActionResultV1, EventEnvelopeV1


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def make_event_envelope(
    *,
    event_type: str,
    source: str,
    payload: dict[str, Any],
    dedupe_key: str,
    event_id: str | None = None,
) -> dict[str, Any]:
    row = {
        "schema": "event_envelope_v1",
        "event_id": event_id or str(uuid.uuid4()),
        "event_type": event_type,
        "source": source,
        "observed_at": utc_now(),
        "dedupe_key": dedupe_key,
        "payload": payload,
    }
    return EventEnvelopeV1.model_validate(row).model_dump(by_alias=True)


def make_action_request(
    *,
    event_id: str,
    action: str,
    args: list[str] | None = None,
    timeout_sec: int = 30,
    retry: str = "none",
    execution_class: str = "transient",
    request_id: str | None = None,
) -> dict[str, Any]:
    row = {
        "schema": "action_request_v1",
        "request_id": request_id or str(uuid.uuid4()),
        "event_id": event_id,
        "action": action,
        "policy": {
            "timeout_sec": int(timeout_sec),
            "retry": retry,
            "execution_class": execution_class,
        },
        "args": list(args or []),
    }
    return ActionRequestV1.model_validate(row).model_dump(by_alias=True)


def make_action_result(
    *,
    event_id: str,
    request_id: str,
    status: str,
    return_code: int,
    started_at: str,
    finished_at: str,
    stdout: str,
    stderr: str,
    action: str,
) -> dict[str, Any]:
    row = {
        "schema": "action_result_v1",
        "request_id": request_id,
        "event_id": event_id,
        "action": action,
        "status": status,
        "return_code": int(return_code),
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": {"stdout": stdout, "stderr": stderr},
    }
    return ActionResultV1.model_validate(row).model_dump(by_alias=True)


def parse_event_envelope(raw: str) -> dict[str, Any]:
    event = json.loads(raw)
    return EventEnvelopeV1.model_validate(event).model_dump(by_alias=True)
