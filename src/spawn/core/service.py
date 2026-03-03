"""spawnd daemon entrypoint."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import logging
import os
import shlex
import subprocess
import time
import tomllib
import uuid
from pathlib import Path
from typing import Any

from dataconfy import ConfigManager
from pydantic import BaseModel, Field, ValidationError
from spawn.contracts.envelopes import make_action_request, parse_event_envelope, utc_now
from spawn.contracts.task_results import make_task_result
from spawn.logging_utils import configure_logging
from spawn.ssot.validate import validate_or_raise
from xdg_base_dirs import xdg_cache_home, xdg_config_home, xdg_state_home


logger = logging.getLogger(__name__)


@dataclass
class CodexSessionRefreshData:
    source_command: str
    refresh_command: str
    topics: list[str]
    debounce_seconds: float
    log_path: str
    execution_mode: str


@dataclass
class SpawnConfigData:
    codex_session_refresh: CodexSessionRefreshData


class CodexSessionRefreshModel(BaseModel):
    source_command: str = "python3 -m spawn.runtime.codex_event_source"
    refresh_command: str = "codex-refresh-context --wait-session-write"
    topics: list[str] = Field(
        default_factory=lambda: ["codex.session.started", "codex.session.ended"]
    )
    debounce_seconds: float = 2.0
    log_path: str
    execution_mode: str = "transient"


class SpawnConfigModel(BaseModel):
    codex_session_refresh: CodexSessionRefreshModel


def xdg_path(var: str, fallback: str) -> Path:
    if var == "XDG_CACHE_HOME":
        return xdg_cache_home()
    if var == "XDG_CONFIG_HOME":
        return xdg_config_home()
    if var == "XDG_STATE_HOME":
        return xdg_state_home()
    return Path(os.environ.get(var, fallback)).expanduser()


def default_config_path() -> Path:
    return xdg_path("XDG_CONFIG_HOME", "~/.config") / "spawn" / "spawnd.toml"


def default_values() -> dict[str, Any]:
    xdg_state = xdg_path("XDG_STATE_HOME", "~/.local/state")
    return {
        "codex_session_refresh": {
            "source_command": "python3 -m spawn.runtime.codex_event_source",
            "refresh_command": "codex-refresh-context --wait-session-write",
            "topics": ["codex.session.started", "codex.session.ended"],
            "debounce_seconds": 2.0,
            "log_path": str(xdg_state / "spawn" / "spawnd-codex-session-refresh.jsonl"),
            "execution_mode": "transient",
        }
    }


def default_toml_text() -> str:
    cfg = default_values()["codex_session_refresh"]
    topics = ", ".join(f'"{topic}"' for topic in cfg["topics"])
    lines = [
        "[codex_session_refresh]",
        f'source_command = "{cfg["source_command"]}"',
        f'refresh_command = "{cfg["refresh_command"]}"',
        f"topics = [{topics}]",
        f"debounce_seconds = {float(cfg['debounce_seconds']):.1f}",
        f'log_path = "{cfg["log_path"]}"',
        f'execution_mode = "{cfg["execution_mode"]}"',
        "",
    ]
    return "\n".join(lines)


def write_default_config(path: Path, *, force: bool = False) -> None:
    if path.exists() and not force:
        raise SystemExit(
            f"config already exists: {path} (use --write-config --force to overwrite)"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(default_toml_text(), encoding="utf-8")


def load_config_via_dataconfy(path: Path) -> dict[str, Any] | None:
    if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
        return None
    cfg = default_values()
    c = cfg["codex_session_refresh"]
    defaults = SpawnConfigData(
        codex_session_refresh=CodexSessionRefreshData(
            source_command=str(c["source_command"]),
            refresh_command=str(c["refresh_command"]),
            topics=[str(t) for t in c["topics"]],
            debounce_seconds=float(c["debounce_seconds"]),
            log_path=str(c["log_path"]),
            execution_mode=str(c["execution_mode"]),
        )
    )
    mgr = ConfigManager(app_name="spawn", config_dir=path.parent, use_env_vars=True)
    loaded = mgr.load(SpawnConfigData, filename=path.name)
    merged = loaded if loaded is not None else defaults
    return asdict(merged)


def load_config(path: Path) -> dict[str, Any]:
    cfg = default_values()
    if not path.exists():
        loaded = {}
    elif path.suffix.lower() in {".yaml", ".yml", ".json"}:
        loaded = load_config_via_dataconfy(path) or {}
    else:
        loaded = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        loaded = {}
    section = loaded.get("codex_session_refresh")
    if isinstance(section, dict):
        cfg["codex_session_refresh"].update(section)
    try:
        validated = SpawnConfigModel.model_validate(cfg)
        return validated.model_dump()
    except ValidationError as exc:
        raise SystemExit(f"invalid config: {exc}") from exc


def append_log(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def to_ssot_event(event: dict[str, Any], run_id: str) -> dict[str, Any]:
    row = {
        "schema_name": "event.envelope",
        "schema_version": "v1",
        "event_id": str(event.get("event_id", "")),
        "request_id": "",
        "ts": str(event.get("observed_at", utc_now())),
        "topic": str(event.get("event_type", "")),
        "source": str(event.get("source", "spawn.codex-event-source")),
        "run_id": run_id,
        "dedupe_key": str(event.get("dedupe_key", "")),
        "payload": event.get("payload", {}),
    }
    return row


def iter_jsonl_from_command(command: str):
    proc = subprocess.Popen(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.strip()
            if line:
                yield line
    finally:
        proc.terminate()


def run_command(command: str) -> tuple[int, str, str]:
    cp = subprocess.run(
        shlex.split(command),
        capture_output=True,
        text=True,
        check=False,
    )
    return cp.returncode, cp.stdout.strip(), cp.stderr.strip()


def unit_name_for_request(request_id: str) -> str:
    clean = "".join(ch for ch in request_id if ch.isalnum() or ch in {"-", "_"})
    return f"spawn-task@codex-session-refresh-{clean}.service"


def dispatch_transient_refresh(
    *,
    request_id: str,
    event_id: str,
    refresh_command: str,
    log_path: Path,
) -> tuple[int, str, str]:
    cmd = [
        "systemd-run",
        "--user",
        "--quiet",
        "--unit",
        unit_name_for_request(request_id),
        "--property",
        "Slice=spawn.slice",
        "--property",
        "NoNewPrivileges=yes",
        "--property",
        "PrivateTmp=yes",
        os.environ.get(
            "SPAWNCTL_BIN", str(Path.home() / ".local" / "bin" / "spawnctl")
        ),
        "__internal",
        "run-refresh",
        "--request-id",
        request_id,
        "--event-id",
        event_id,
        "--refresh-command",
        refresh_command,
        "--log-path",
        str(log_path),
    ]
    cp = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return cp.returncode, cp.stdout.strip(), cp.stderr.strip()


def cmd_codex_refresh(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser()
    if args.write_config:
        write_default_config(config_path, force=args.force)
        logger.info("default config written", extra={"path": str(config_path)})
        print(config_path)
        return 0

    cfg = load_config(config_path)
    section = cfg["codex_session_refresh"]

    source_command = args.source_command or str(
        section.get("source_command", "python3 -m spawn.runtime.codex_event_source")
    )
    refresh_command = args.refresh_command or str(
        section.get("refresh_command", "codex-refresh-context --wait-session-write")
    )
    debounce_seconds = (
        args.debounce_seconds
        if args.debounce_seconds is not None
        else float(section.get("debounce_seconds", 2.0))
    )
    topics_arg = args.topics
    if topics_arg:
        topics = {item.strip() for item in topics_arg.split(",") if item.strip()}
    else:
        raw_topics = section.get("topics", [])
        topics = {str(item).strip() for item in raw_topics if str(item).strip()}
    log_path = Path(args.log_path or str(section.get("log_path"))).expanduser()
    execution_mode = (
        (args.execution_mode or str(section.get("execution_mode", "transient")))
        .strip()
        .lower()
    )
    logger.info(
        "starting codex session refresh loop",
        extra={
            "config_path": str(config_path),
            "execution_mode": execution_mode,
            "topics_count": len(topics),
        },
    )

    xdg_path("XDG_CACHE_HOME", "~/.cache").joinpath("spawn").mkdir(
        parents=True, exist_ok=True
    )
    xdg_path("XDG_STATE_HOME", "~/.local/state").joinpath("spawn").mkdir(
        parents=True, exist_ok=True
    )

    last_run = 0.0
    for line in iter_jsonl_from_command(source_command):
        try:
            event = parse_event_envelope(line)
        except (ValueError, json.JSONDecodeError):
            append_log(
                log_path,
                make_task_result(
                    event_id=str(uuid.uuid4()),
                    request_id=str(uuid.uuid4()),
                    status="FAIL",
                    return_code=1,
                    started_at=utc_now(),
                    finished_at=utc_now(),
                    stdout="",
                    stderr="invalid event_envelope_v1 line",
                    reason_code="DETERMINISTIC.SCHEMA_INVALID",
                ),
            )
            continue

        try:
            validate_or_raise(
                "event.envelope", to_ssot_event(event, run_id="codex-session-refresh")
            )
        except Exception as exc:
            append_log(
                log_path,
                make_task_result(
                    event_id=str(event.get("event_id", str(uuid.uuid4()))),
                    request_id=str(uuid.uuid4()),
                    status="FAIL",
                    return_code=1,
                    started_at=utc_now(),
                    finished_at=utc_now(),
                    stdout="",
                    stderr=f"event validation failed: {exc}",
                    reason_code="DETERMINISTIC.SCHEMA_INVALID",
                ),
            )
            continue

        topic = event.get("event_type")
        if not isinstance(topic, str) or topic not in topics:
            continue

        now = time.monotonic()
        if (now - last_run) < debounce_seconds:
            continue
        last_run = now

        request = make_action_request(
            event_id=str(event.get("event_id", "")),
            action="codex.refresh_context",
            args=shlex.split(refresh_command),
            timeout_sec=30,
            retry="none",
            execution_class=execution_mode,
        )
        work_queue = {
            "schema_name": "work.queue",
            "schema_version": "v1",
            "run_id": f"run-{request['request_id']}",
            "base_ref": str(request["event_id"]),
            "max_workers": 1,
            "tasks": [
                {
                    "task_id": str(request["request_id"]),
                    "goal": refresh_command,
                    "status": "QUEUED",
                }
            ],
        }
        try:
            validate_or_raise("work.queue", work_queue)
        except Exception as exc:
            append_log(
                log_path,
                make_task_result(
                    event_id=str(request["event_id"]),
                    request_id=str(request["request_id"]),
                    status="FAIL",
                    return_code=1,
                    started_at=utc_now(),
                    finished_at=utc_now(),
                    stdout="",
                    stderr=f"pre-dispatch validation failed: {exc}",
                    reason_code="DETERMINISTIC.SCHEMA_INVALID",
                ),
            )
            continue
        if execution_mode == "transient":
            started = utc_now()
            rc, out, err = dispatch_transient_refresh(
                request_id=request["request_id"],
                event_id=request["event_id"],
                refresh_command=refresh_command,
                log_path=log_path,
            )
            finished = utc_now()
            append_log(
                log_path,
                make_task_result(
                    event_id=request["event_id"],
                    request_id=request["request_id"],
                    status="DISPATCHED" if rc == 0 else "DISPATCH_FAILED",
                    return_code=rc,
                    started_at=started,
                    finished_at=finished,
                    stdout=out,
                    stderr=err,
                    reason_code="DETERMINISTIC.OK"
                    if rc == 0
                    else "INFRA.DISPATCH_FAILED",
                ),
            )
            logger.debug(
                "dispatched transient refresh",
                extra={
                    "request_id": request["request_id"],
                    "event_id": request["event_id"],
                    "rc": rc,
                },
            )
            continue

        started = utc_now()
        rc, out, err = run_command(refresh_command)
        finished = utc_now()
        append_log(
            log_path,
            make_task_result(
                event_id=request["event_id"],
                request_id=request["request_id"],
                status="PASS" if rc == 0 else "FAIL",
                return_code=rc,
                started_at=started,
                finished_at=finished,
                stdout=out,
                stderr=err,
                reason_code="DETERMINISTIC.OK" if rc == 0 else "TRANSIENT.CMD_FAILED",
            ),
        )
        logger.debug(
            "executed in-process refresh",
            extra={
                "request_id": request["request_id"],
                "event_id": request["event_id"],
                "rc": rc,
            },
        )
    return 0


def cmd_api_serve(args: argparse.Namespace) -> int:
    from spawn.adapters.grpc_server import serve

    socket_path = Path(args.socket_path).expanduser()
    logger.info("starting grpc api", extra={"socket_path": str(socket_path)})
    return serve(socket_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser(
        "codex-session-refresh", help="Refresh codex context on session events"
    )
    p.add_argument("--config", default=str(default_config_path()))
    p.add_argument(
        "--write-config",
        action="store_true",
        help="Write default config to --config and exit.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite when used with --write-config.",
    )
    p.add_argument("--source-command", default="")
    p.add_argument("--refresh-command", default="")
    p.add_argument("--topics", default="", help="Comma-separated topics.")
    p.add_argument("--debounce-seconds", type=float, default=None)
    p.add_argument("--log-path", default="")
    p.add_argument("--execution-mode", choices=["transient", "in_process"], default="")
    p.set_defaults(func=cmd_codex_refresh)

    p_api = sub.add_parser("api-serve", help="Run gRPC control API over Unix socket")
    p_api.add_argument(
        "--socket-path",
        default=os.environ.get(
            "SPAWN_SOCKET_PATH", f"/run/user/{os.getuid()}/spawn/spawn.sock"
        ),
    )
    p_api.set_defaults(func=cmd_api_serve)

    return parser


def main() -> int:
    configure_logging(app_name="spawnd", default_format="json")
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
