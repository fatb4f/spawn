"""Daemon command group."""

from __future__ import annotations

import json

import typer

from spawn.adapters.grpc_server import serve
from spawn.cli.shared import channel_and_stub, console, socket_path
from spawn.v1 import spawn_control_pb2 as pb2

app = typer.Typer(help="Daemon control helpers")


@app.command("serve-api")
def serve_api(
    socket_path_value: str = typer.Option("", "--socket-path", help="Unix socket path"),
) -> None:
    raise typer.Exit(serve(socket_path(socket_path_value)))


@app.command("health")
def health(
    socket_path_value: str = typer.Option("", "--socket-path", help="Unix socket path"),
    as_json: bool = typer.Option(False, "--json", help="Print JSON result"),
) -> None:
    try:
        channel, stub = channel_and_stub(socket_path_value)
        try:
            resp = stub.Health(pb2.HealthRequest(), timeout=2)
            ok, message = bool(resp.ok), resp.message
        finally:
            channel.close()
    except Exception as exc:
        console.print(f"daemon unavailable: {exc}", style="red")
        raise typer.Exit(1) from exc

    if as_json:
        console.print_json(json.dumps({"ok": ok, "message": message}, sort_keys=True))
    else:
        console.print(message)
    raise typer.Exit(0 if ok else 1)

