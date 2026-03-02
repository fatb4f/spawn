"""spawnctl user-facing control CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import grpc

from spawn.runtime import codex_session_ops
from spawn.adapters.grpc_server import default_socket_path, grpc_target_from_path
from spawn.v1 import spawn_control_pb2 as pb2
from spawn.v1 import spawn_control_pb2_grpc as pb2_grpc


def default_socket_path_str() -> str:
    return str(default_socket_path())


def _channel_and_stub(path: str):
    target = grpc_target_from_path(Path(path).expanduser() if path else default_socket_path())
    channel = grpc.insecure_channel(target)
    return channel, pb2_grpc.SpawnControlStub(channel)


def cmd_run_transient_refresh(args: argparse.Namespace) -> int:
    return codex_session_ops.run_transient_worker(
        request_id=args.request_id,
        event_id=args.event_id,
        refresh_command=args.refresh_command,
        log_path=args.log_path,
    )


def cmd_daemon_serve_api(args: argparse.Namespace) -> int:
    from spawn.adapters.grpc_server import serve

    return serve(Path(args.socket_path).expanduser())


def cmd_daemon_health(args: argparse.Namespace) -> int:
    try:
        channel, stub = _channel_and_stub(args.socket_path)
        try:
            resp = stub.Health(pb2.HealthRequest(), timeout=2)
            ok, msg = bool(resp.ok), resp.message
        finally:
            channel.close()
    except Exception as exc:
        print(f"daemon unavailable: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"ok": ok, "message": msg}, sort_keys=True))
    else:
        print(msg)
    return 0 if ok else 1


def cmd_codex_session_refresh(args: argparse.Namespace) -> int:
    try:
        channel, stub = _channel_and_stub(args.socket_path)
        try:
            resp = stub.CodexSessionRefresh(
                pb2.CodexSessionRefreshRequest(
                    request_id=args.request_id,
                    event_id=args.event_id,
                    refresh_command=args.refresh_command,
                    log_path=args.log_path,
                    wait=args.wait,
                ),
                timeout=8,
            )
        finally:
            channel.close()
    except Exception as exc:
        print(f"daemon unavailable: {exc}", file=sys.stderr)
        return 1
    if not resp.ok:
        print(resp.message or "failed", file=sys.stderr)
        return int(resp.return_code or 1)
    print(resp.request_id)
    return 0


def cmd_codex_session_status(args: argparse.Namespace) -> int:
    try:
        channel, stub = _channel_and_stub(args.socket_path)
        try:
            resp = stub.CodexSessionStatus(
                pb2.CodexSessionStatusRequest(
                    request_id=args.request_id,
                    log_path=args.log_path,
                    wait_seconds=args.wait_seconds,
                ),
                timeout=max(2, int(args.wait_seconds) + 2),
            )
        finally:
            channel.close()
    except Exception as exc:
        print(f"daemon unavailable: {exc}", file=sys.stderr)
        return 1
    if not resp.ok:
        print(resp.message or "not found", file=sys.stderr)
        return 1
    try:
        row = json.loads(resp.row_json)
        print(json.dumps(row, sort_keys=True, indent=2))
    except json.JSONDecodeError:
        print(resp.row_json)
    return 0


def cmd_codex_session_logs(args: argparse.Namespace) -> int:
    try:
        channel, stub = _channel_and_stub(args.socket_path)
        try:
            resp = stub.CodexSessionLogs(
                pb2.CodexSessionLogsRequest(request_id=args.request_id, lines=args.lines),
                timeout=5,
            )
        finally:
            channel.close()
    except Exception as exc:
        print(f"daemon unavailable: {exc}", file=sys.stderr)
        return 1
    if not resp.ok:
        print(resp.message or "failed", file=sys.stderr)
        return int(resp.return_code or 1)
    print(resp.logs, end="")
    return 0


def cmd_codex_session_list(args: argparse.Namespace) -> int:
    try:
        channel, stub = _channel_and_stub(args.socket_path)
        try:
            resp = stub.CodexSessionList(pb2.CodexSessionListRequest(log_path=args.log_path), timeout=5)
        finally:
            channel.close()
    except Exception as exc:
        print(f"daemon unavailable: {exc}", file=sys.stderr)
        return 1
    if not resp.ok:
        print(resp.message or "failed", file=sys.stderr)
        return 1
    try:
        rows = json.loads(resp.rows_json) if resp.rows_json else []
    except json.JSONDecodeError:
        rows = []
    print(json.dumps(rows, sort_keys=True, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    hidden = sub.add_parser("__run-codex-session-refresh", help=argparse.SUPPRESS)
    hidden.add_argument("--request-id", required=True)
    hidden.add_argument("--event-id", required=True)
    hidden.add_argument("--refresh-command", required=True)
    hidden.add_argument("--log-path", required=True)
    hidden.set_defaults(func=cmd_run_transient_refresh)

    daemon = sub.add_parser("daemon", help="Daemon control helpers")
    daemon_sub = daemon.add_subparsers(dest="daemon_cmd", required=True)

    d_serve = daemon_sub.add_parser("serve-api", help="Serve gRPC API on unix socket")
    d_serve.add_argument("--socket-path", default=default_socket_path_str())
    d_serve.set_defaults(func=cmd_daemon_serve_api)

    d_health = daemon_sub.add_parser("health", help="Probe daemon health via gRPC")
    d_health.add_argument("--socket-path", default=default_socket_path_str())
    d_health.add_argument("--json", action="store_true")
    d_health.set_defaults(func=cmd_daemon_health)

    codex = sub.add_parser("codex-session", help="Codex session actions")
    codex_sub = codex.add_subparsers(dest="codex_cmd", required=True)

    p_refresh = codex_sub.add_parser("refresh", help="Dispatch session refresh as transient unit")
    p_refresh.add_argument("--socket-path", default=default_socket_path_str())
    p_refresh.add_argument("--request-id", default="")
    p_refresh.add_argument("--event-id", default="")
    p_refresh.add_argument("--refresh-command", default="codex-refresh-context --wait-session-write")
    p_refresh.add_argument("--log-path", default="")
    p_refresh.add_argument("--wait", action="store_true")
    p_refresh.set_defaults(func=cmd_codex_session_refresh)

    p_status = codex_sub.add_parser("status", help="Show status for a refresh run")
    p_status.add_argument("--socket-path", default=default_socket_path_str())
    p_status.add_argument("--request-id", default="")
    p_status.add_argument("--log-path", default="")
    p_status.add_argument("--wait-seconds", type=float, default=2.0)
    p_status.set_defaults(func=cmd_codex_session_status)

    p_logs = codex_sub.add_parser("logs", help="Show logs for a refresh run")
    p_logs.add_argument("--socket-path", default=default_socket_path_str())
    p_logs.add_argument("--request-id", default="")
    p_logs.add_argument("--lines", type=int, default=100)
    p_logs.set_defaults(func=cmd_codex_session_logs)

    p_list = codex_sub.add_parser("list", help="List recent refresh runs")
    p_list.add_argument("--socket-path", default=default_socket_path_str())
    p_list.add_argument("--log-path", default="")
    p_list.set_defaults(func=cmd_codex_session_list)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
