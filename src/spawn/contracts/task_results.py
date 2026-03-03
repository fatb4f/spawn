"""Task result contract helpers."""

from __future__ import annotations

from typing import Any

from spawn.ssot.validate import validate_or_raise


def make_task_result(
    *,
    request_id: str,
    event_id: str,
    status: str,
    return_code: int,
    started_at: str,
    finished_at: str,
    stdout: str,
    stderr: str,
    reason_code: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_name": "task.result",
        "schema_version": "v1",
        "run_id": f"run-{request_id}",
        "task_id": "codex.refresh_context",
        "request_id": request_id,
        "event_id": event_id,
        "status": status,
        "return_code": int(return_code),
        "started_at": started_at,
        "finished_at": finished_at,
        "stdout": stdout,
        "stderr": stderr,
        "reason_code": reason_code,
    }
    validate_or_raise("task.result", row)
    return row
