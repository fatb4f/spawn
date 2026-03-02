"""Spawn contract helpers for event/action envelopes."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any


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
    return {
        "schema": "event_envelope_v1",
        "event_id": event_id or str(uuid.uuid4()),
        "event_type": event_type,
        "source": source,
        "observed_at": utc_now(),
        "dedupe_key": dedupe_key,
        "payload": payload,
    }


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
    return {
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
    return {
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


def parse_event_envelope(raw: str) -> dict[str, Any]:
    event = json.loads(raw)
    if not isinstance(event, dict):
        raise ValueError("event must be an object")
    if event.get("schema") != "event_envelope_v1":
        raise ValueError("unsupported schema")
    for key in ("event_id", "event_type", "source", "observed_at", "dedupe_key", "payload"):
        if key not in event:
            raise ValueError(f"missing required key: {key}")
    return event
