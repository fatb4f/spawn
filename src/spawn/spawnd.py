"""spawnd daemon entrypoint."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
import shlex
import subprocess
import time
import tomllib
import uuid
from pathlib import Path
from typing import Any

from spawn.contracts import make_action_request, make_action_result, parse_event_envelope, utc_now

try:
    from dataconfy import ConfigManager
except ImportError:  # pragma: no cover - optional dependency
    ConfigManager = None

try:
    from pydantic import BaseModel, Field, ValidationError
except ImportError:  # pragma: no cover - optional dependency
    BaseModel = None
    Field = None
    ValidationError = Exception

try:
    from xdg_base_dirs import xdg_cache_home, xdg_config_home, xdg_state_home
except ImportError:  # pragma: no cover - optional dependency
    xdg_cache_home = xdg_config_home = xdg_state_home = None


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


if BaseModel is not None:
    class CodexSessionRefreshModel(BaseModel):
        source_command: str = "python3 -m spawn.codex_event_source"
        refresh_command: str = "codex-refresh-context --wait-session-write"
        topics: list[str] = Field(default_factory=lambda: ["codex.session.started", "codex.session.ended"])
        debounce_seconds: float = 2.0
        log_path: str
        execution_mode: str = "transient"

    class SpawnConfigModel(BaseModel):
        codex_session_refresh: CodexSessionRefreshModel


def xdg_path(var: str, fallback: str) -> Path:
    if var == "XDG_CACHE_HOME" and xdg_cache_home is not None:
        return xdg_cache_home()
    if var == "XDG_CONFIG_HOME" and xdg_config_home is not None:
        return xdg_config_home()
    if var == "XDG_STATE_HOME" and xdg_state_home is not None:
        return xdg_state_home()
    return Path(os.environ.get(var, fallback)).expanduser()


def default_config_path() -> Path:
    return xdg_path("XDG_CONFIG_HOME", "~/.config") / "spawn" / "spawnd.toml"


def default_values() -> dict[str, Any]:
    xdg_state = xdg_path("XDG_STATE_HOME", "~/.local/state")
    return {
        "codex_session_refresh": {
            "source_command": "python3 -m spawn.codex_event_source",
            "refresh_command": "codex-refresh-context --wait-session-write",
            "topics": ["codex.session.started", "codex.session.ended"],
            "debounce_seconds": 2.0,
            "log_path": str(xdg_state / "spawn" / "spawnd-codex-session-refresh.jsonl"),
            "execution_mode": "transient",
        }
    }


def load_config_via_dataconfy(path: Path) -> dict[str, Any] | None:
    if ConfigManager is None:
        return None
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
    if BaseModel is not None:
        try:
            validated = SpawnConfigModel.model_validate(cfg)
            return validated.model_dump()
        except ValidationError as exc:
            raise SystemExit(f"invalid config: {exc}") from exc
    return cfg


def append_log(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


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
        os.environ.get("SPAWNCTL_BIN", str(Path.home() / ".local" / "bin" / "spawnctl")),
        "__run-codex-session-refresh",
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
    cfg = load_config(Path(args.config).expanduser())
    section = cfg["codex_session_refresh"]

    source_command = args.source_command or str(section.get("source_command", "python3 -m spawn.codex_event_source"))
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
    execution_mode = (args.execution_mode or str(section.get("execution_mode", "transient"))).strip().lower()

    xdg_path("XDG_CACHE_HOME", "~/.cache").joinpath("spawn").mkdir(parents=True, exist_ok=True)
    xdg_path("XDG_STATE_HOME", "~/.local/state").joinpath("spawn").mkdir(parents=True, exist_ok=True)

    last_run = 0.0
    for line in iter_jsonl_from_command(source_command):
        try:
            event = parse_event_envelope(line)
        except (ValueError, json.JSONDecodeError):
            append_log(
                log_path,
                make_action_result(
                    event_id=str(uuid.uuid4()),
                    request_id=str(uuid.uuid4()),
                    status="invalid_event",
                    return_code=1,
                    started_at=utc_now(),
                    finished_at=utc_now(),
                    stdout="",
                    stderr="invalid event_envelope_v1 line",
                    action="codex.refresh_context",
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
                make_action_result(
                    event_id=request["event_id"],
                    request_id=request["request_id"],
                    status="dispatched" if rc == 0 else "dispatch_failed",
                    return_code=rc,
                    started_at=started,
                    finished_at=finished,
                    stdout=out,
                    stderr=err,
                    action="codex.refresh_context.dispatch",
                ),
            )
            continue

        started = utc_now()
        rc, out, err = run_command(refresh_command)
        finished = utc_now()
        append_log(
            log_path,
            make_action_result(
                event_id=request["event_id"],
                request_id=request["request_id"],
                status="ok" if rc == 0 else "failed",
                return_code=rc,
                started_at=started,
                finished_at=finished,
                stdout=out,
                stderr=err,
                action=request["action"],
            ),
        )
    return 0


def cmd_api_serve(args: argparse.Namespace) -> int:
    from spawn.grpc_server import serve

    socket_path = Path(args.socket_path).expanduser()
    return serve(socket_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("codex-session-refresh", help="Refresh codex context on session events")
    p.add_argument("--config", default=str(default_config_path()))
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
        default=os.environ.get("SPAWN_SOCKET_PATH", f"/run/user/{os.getuid()}/spawn/spawn.sock"),
    )
    p_api.set_defaults(func=cmd_api_serve)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
