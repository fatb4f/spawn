"""Emit Codex-related spawn events as JSONL."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spawn.contracts import make_event_envelope, utc_now


@dataclass
class SourceState:
    known_sessions: set[str]
    session_mtime: dict[str, float]
    codex_running: bool
    last_stall_emit: float
    refresh_pos: int
    refresh_inode: int | None
    prompt_hash: str | None
    config_hash: str | None
    service_restarts: dict[str, int]
    last_service_poll: float


def emit(topic: str, payload: dict[str, Any]) -> None:
    dedupe_value = (
        payload.get("path")
        or payload.get("service")
        or payload.get("sha256")
        or payload.get("line")
        or payload.get("latest_path")
        or payload.get("by")
        or "generic"
    )
    event = make_event_envelope(
        event_type=topic,
        source="spawn.codex-event-source",
        payload={"ts": utc_now(), **payload},
        dedupe_key=f"{topic}:{dedupe_value}",
    )
    print(json.dumps(event, sort_keys=True), flush=True)


def file_hash(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def list_session_files(sessions_root: Path) -> list[Path]:
    if not sessions_root.exists():
        return []
    return sorted(
        [p for p in sessions_root.rglob("*.jsonl") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )


def is_codex_running() -> bool:
    cp = subprocess.run(["pgrep", "-x", "codex"], capture_output=True, text=True, check=False)
    return cp.returncode == 0


def read_new_refresh_lines(path: Path, state: SourceState) -> list[str]:
    if not path.exists() or not path.is_file():
        state.refresh_pos = 0
        state.refresh_inode = None
        return []

    st = path.stat()
    inode = int(st.st_ino)
    size = int(st.st_size)
    if state.refresh_inode != inode or state.refresh_pos > size:
        state.refresh_pos = 0
        state.refresh_inode = inode

    if size == state.refresh_pos:
        return []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(state.refresh_pos)
        chunk = f.read()
        state.refresh_pos = f.tell()
    return [line.strip() for line in chunk.splitlines() if line.strip()]


def read_user_service_restarts(service_name: str) -> int | None:
    cp = subprocess.run(
        ["systemctl", "--user", "show", service_name, "-p", "NRestarts", "--value"],
        capture_output=True,
        text=True,
        check=False,
    )
    if cp.returncode != 0:
        return None
    raw = cp.stdout.strip()
    if not raw.isdigit():
        return None
    return int(raw)


def main() -> int:
    sessions_root = Path(os.environ.get("CODEX_SESSIONS_ROOT", "~/.config/codex/sessions")).expanduser()
    codex_state = Path(os.environ.get("CODEX_STATE", "~/.local/state/codex")).expanduser()
    refresh_log = codex_state / "meta" / "refresh.log"
    prompt_path = codex_state / "meta" / "effective_prompt.txt"
    config_path = Path(os.environ.get("CODEX_CONFIG_PATH", "~/.config/codex/config.toml")).expanduser()
    poll_seconds = float(os.environ.get("CODEX_EVENT_POLL_SECONDS", "1"))
    stall_seconds = int(os.environ.get("CODEX_STALL_SECONDS", "900"))
    services = [
        item.strip()
        for item in os.environ.get(
            "WATCH_SERVICES",
            "spawnd-codex-session-refresh.service",
        ).split(",")
        if item.strip()
    ]

    state = SourceState(
        known_sessions=set(),
        session_mtime={},
        codex_running=False,
        last_stall_emit=0.0,
        refresh_pos=0,
        refresh_inode=None,
        prompt_hash=None,
        config_hash=None,
        service_restarts={},
        last_service_poll=0.0,
    )

    while True:
        files = list_session_files(sessions_root)
        latest_mtime = 0.0
        latest_path = None
        for path in files:
            mtime = path.stat().st_mtime
            latest_mtime = max(latest_mtime, mtime)
            latest_path = path if latest_path is None or mtime >= latest_mtime else latest_path
            key = str(path)
            old = state.session_mtime.get(key)
            if key not in state.known_sessions:
                state.known_sessions.add(key)
                state.session_mtime[key] = mtime
                emit("codex.session.started", {"path": key, "mtime_epoch": int(mtime)})
            elif old is not None and mtime > old:
                state.session_mtime[key] = mtime
                emit("codex.session.updated", {"path": key, "mtime_epoch": int(mtime)})

        running = is_codex_running()
        if running and not state.codex_running:
            emit("codex.session.started", {"by": "process"})
        if (not running) and state.codex_running:
            emit("codex.session.ended", {"by": "process"})
        state.codex_running = running

        if running and latest_mtime > 0:
            age = time.time() - latest_mtime
            if age >= stall_seconds and (time.time() - state.last_stall_emit) >= max(60, stall_seconds // 2):
                emit(
                    "codex.session.stalled",
                    {
                        "latest_path": str(latest_path) if latest_path else None,
                        "seconds_since_session_write": int(age),
                    },
                )
                state.last_stall_emit = time.time()

        for line in read_new_refresh_lines(refresh_log, state):
            lowered = line.lower()
            if "warn: context generator failed" in lowered or "error" in lowered:
                emit("codex.meta.refresh.failed", {"line": line})
            if "resume" in lowered and ("fail" in lowered or "error" in lowered):
                emit("codex.resume.failed", {"line": line})

        current_prompt_hash = file_hash(prompt_path)
        if state.prompt_hash is None:
            state.prompt_hash = current_prompt_hash
        elif current_prompt_hash is not None and current_prompt_hash != state.prompt_hash:
            emit(
                "codex.meta.prompt.changed",
                {"path": str(prompt_path), "sha256": current_prompt_hash},
            )
            state.prompt_hash = current_prompt_hash

        current_config_hash = file_hash(config_path)
        if state.config_hash is None:
            state.config_hash = current_config_hash
        elif current_config_hash is not None and current_config_hash != state.config_hash:
            emit(
                "codex.config.changed",
                {"path": str(config_path), "sha256": current_config_hash},
            )
            state.config_hash = current_config_hash

        now = time.time()
        if now - state.last_service_poll >= 5:
            state.last_service_poll = now
            for service_name in services:
                restarts = read_user_service_restarts(service_name)
                if restarts is None:
                    continue
                prev = state.service_restarts.get(service_name)
                if prev is None:
                    state.service_restarts[service_name] = restarts
                elif restarts > prev:
                    state.service_restarts[service_name] = restarts
                    emit(
                        "codex.watcher.service.restarted",
                        {"service": service_name, "restarts": restarts},
                    )

        time.sleep(poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
