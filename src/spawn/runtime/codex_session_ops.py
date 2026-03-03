"""Shared codex-session operation helpers."""

from __future__ import annotations

import json
import logging
import subprocess
import time
import uuid
from pathlib import Path

from spawn.contracts.task_results import make_task_result
from spawn.contracts.envelopes import utc_now
from spawn.core import service as spawnd
from spawn.ssot.validate import validate_or_raise

logger = logging.getLogger(__name__)


def default_log_path() -> Path:
    cfg = spawnd.default_values()
    return Path(cfg["codex_session_refresh"]["log_path"]).expanduser()


def append_log(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def latest_request_id(path: Path) -> str | None:
    if not path.exists():
        return None
    last = None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = row.get("request_id")
            if isinstance(rid, str) and rid:
                last = rid
    return last


def latest_result_for_request(path: Path, request_id: str) -> dict | None:
    if not path.exists():
        return None
    latest = None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("request_id") == request_id:
                latest = row
    return latest


def run_transient_worker(
    request_id: str, event_id: str, refresh_command: str, log_path: Path | str
) -> int:
    path = Path(log_path).expanduser()
    queue_payload = {
        "schema_name": "work.queue",
        "schema_version": "v1",
        "run_id": f"run-{request_id}",
        "base_ref": event_id or "manual",
        "max_workers": 1,
        "tasks": [
            {
                "task_id": "codex.refresh_context",
                "goal": refresh_command,
                "status": "RUNNING",
            }
        ],
    }
    validate_or_raise("work.queue", queue_payload)

    started = utc_now()
    rc, out, err = spawnd.run_command(refresh_command)
    finished = utc_now()
    append_log(
        path,
        make_task_result(
            event_id=event_id,
            request_id=request_id,
            status="PASS" if rc == 0 else "FAIL",
            return_code=rc,
            started_at=started,
            finished_at=finished,
            stdout=out,
            stderr=err,
            reason_code="DETERMINISTIC.OK" if rc == 0 else "TRANSIENT.CMD_FAILED",
        ),
    )
    return rc


def dispatch_refresh(
    request_id: str | None, event_id: str | None, refresh_command: str, log_path: Path
) -> tuple[int, str, str, str]:
    rid = request_id or str(uuid.uuid4())
    eid = event_id or f"manual-{rid}"
    rc, out, err = spawnd.dispatch_transient_refresh(
        request_id=rid,
        event_id=eid,
        refresh_command=refresh_command,
        log_path=log_path,
    )
    logger.debug(
        "refresh dispatched", extra={"request_id": rid, "event_id": eid, "rc": rc}
    )
    return rc, out, err, rid


def resolve_request_id(request_id: str, log_path: Path) -> str | None:
    if request_id:
        return request_id
    return latest_request_id(log_path)


def status_row(request_id: str, log_path: Path, wait_seconds: float) -> dict | None:
    deadline = time.time() + max(0.0, float(wait_seconds))
    row = latest_result_for_request(log_path, request_id)
    while row is None and time.time() < deadline:
        time.sleep(0.2)
        row = latest_result_for_request(log_path, request_id)
    return row


def list_rows(log_path: Path, limit: int = 20) -> list[dict]:
    if not log_path.exists():
        return []
    seen: dict[str, dict] = {}
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = row.get("request_id")
            if isinstance(rid, str) and rid:
                seen[rid] = row
    return list(seen.values())[-limit:]


def read_journal_logs(request_id: str, lines: int) -> tuple[int, str, str]:
    unit = spawnd.unit_name_for_request(request_id)
    cp = subprocess.run(
        ["journalctl", "--user-unit", unit, "-n", str(lines), "--no-pager"],
        capture_output=True,
        text=True,
        check=False,
    )
    return cp.returncode, cp.stdout, cp.stderr
