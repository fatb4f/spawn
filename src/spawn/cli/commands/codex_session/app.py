"""Codex session command group."""

from __future__ import annotations

import json
from typing import Any, cast

import typer

from spawn.cli.shared import channel_and_stub, console
from spawn.runtime import codex_session_ops
from spawn.v1 import spawn_control_pb2 as _pb2

pb2: Any = cast(Any, _pb2)
app = typer.Typer(help="Codex session actions")
internal = typer.Typer(hidden=True)


@internal.command("run-refresh", hidden=True)
def run_refresh(
    request_id: str = typer.Option(..., "--request-id"),
    event_id: str = typer.Option(..., "--event-id"),
    refresh_command: str = typer.Option(..., "--refresh-command"),
    log_path: str = typer.Option(..., "--log-path"),
) -> None:
    rc = codex_session_ops.run_transient_worker(
        request_id=request_id,
        event_id=event_id,
        refresh_command=refresh_command,
        log_path=log_path,
    )
    raise typer.Exit(rc)


@app.command("refresh")
def refresh(
    socket_path_value: str = typer.Option("", "--socket-path", help="Unix socket path"),
    request_id: str = typer.Option("", "--request-id"),
    event_id: str = typer.Option("", "--event-id"),
    trigger: str = typer.Option("manual", "--trigger"),
    refresh_command: str = typer.Option(
        "codex-refresh-context --wait-session-write",
        "--refresh-command",
    ),
    log_path: str = typer.Option("", "--log-path"),
    wait: bool = typer.Option(False, "--wait"),
) -> None:
    try:
        channel, stub = channel_and_stub(socket_path_value)
        try:
            encoded_event_id = codex_session_ops.encode_refresh_event_id(
                trigger=trigger,
                event_id=event_id or None,
            )
            resp = stub.CodexSessionRefresh(
                pb2.CodexSessionRefreshRequest(
                    request_id=request_id,
                    event_id=encoded_event_id,
                    refresh_command=refresh_command,
                    log_path=log_path,
                    wait=wait,
                ),
                timeout=8,
            )
        finally:
            channel.close()
    except Exception as exc:
        console.print(f"daemon unavailable: {exc}", style="red")
        raise typer.Exit(1) from exc

    if not resp.ok:
        console.print(resp.message or "failed", style="red")
        raise typer.Exit(int(resp.return_code or 1))
    console.print(resp.request_id)


@app.command("status")
def status(
    socket_path_value: str = typer.Option("", "--socket-path", help="Unix socket path"),
    request_id: str = typer.Option("", "--request-id"),
    log_path: str = typer.Option("", "--log-path"),
    wait_seconds: float = typer.Option(2.0, "--wait-seconds"),
) -> None:
    try:
        channel, stub = channel_and_stub(socket_path_value)
        try:
            resp = stub.CodexSessionStatus(
                pb2.CodexSessionStatusRequest(
                    request_id=request_id,
                    log_path=log_path,
                    wait_seconds=wait_seconds,
                ),
                timeout=max(2, int(wait_seconds) + 2),
            )
        finally:
            channel.close()
    except Exception as exc:
        console.print(f"daemon unavailable: {exc}", style="red")
        raise typer.Exit(1) from exc

    if not resp.ok:
        console.print(resp.message or "not found", style="red")
        raise typer.Exit(1)
    try:
        row = json.loads(resp.row_json)
        console.print_json(json.dumps(row, sort_keys=True))
    except json.JSONDecodeError:
        console.print(resp.row_json)


@app.command("logs")
def logs(
    socket_path_value: str = typer.Option("", "--socket-path", help="Unix socket path"),
    request_id: str = typer.Option("", "--request-id"),
    lines: int = typer.Option(100, "--lines"),
) -> None:
    try:
        channel, stub = channel_and_stub(socket_path_value)
        try:
            resp = stub.CodexSessionLogs(
                pb2.CodexSessionLogsRequest(request_id=request_id, lines=lines),
                timeout=5,
            )
        finally:
            channel.close()
    except Exception as exc:
        console.print(f"daemon unavailable: {exc}", style="red")
        raise typer.Exit(1) from exc

    if not resp.ok:
        console.print(resp.message or "failed", style="red")
        raise typer.Exit(int(resp.return_code or 1))
    console.print(resp.logs, end="")


@app.command("list")
def list_runs(
    socket_path_value: str = typer.Option("", "--socket-path", help="Unix socket path"),
    log_path: str = typer.Option("", "--log-path"),
) -> None:
    try:
        channel, stub = channel_and_stub(socket_path_value)
        try:
            resp = stub.CodexSessionList(
                pb2.CodexSessionListRequest(log_path=log_path), timeout=5
            )
        finally:
            channel.close()
    except Exception as exc:
        console.print(f"daemon unavailable: {exc}", style="red")
        raise typer.Exit(1) from exc

    if not resp.ok:
        console.print(resp.message or "failed", style="red")
        raise typer.Exit(1)
    try:
        rows = json.loads(resp.rows_json) if resp.rows_json else []
    except json.JSONDecodeError:
        rows = []
    console.print_json(json.dumps(rows, sort_keys=True))
