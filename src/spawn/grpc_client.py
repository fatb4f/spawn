"""gRPC client helpers for spawn control plane."""

from __future__ import annotations

import json
import os
from pathlib import Path

import grpc

from spawn.grpc_server import default_socket_path, grpc_target_from_path
from spawn.v1 import spawn_control_pb2 as pb2
from spawn.v1 import spawn_control_pb2_grpc as pb2_grpc


def socket_path(path: str = "") -> Path:
    if path:
        return Path(path).expanduser()
    env_path = os.environ.get("SPAWN_SOCKET_PATH", "")
    if env_path:
        return Path(env_path).expanduser()
    return default_socket_path()


def with_stub(path: str = ""):
    target = grpc_target_from_path(socket_path(path))
    channel = grpc.insecure_channel(target)
    return channel, pb2_grpc.SpawnControlStub(channel)


def health(path: str = "") -> tuple[bool, str]:
    channel, stub = with_stub(path)
    try:
        resp = stub.Health(pb2.HealthRequest(), timeout=2)
        return bool(resp.ok), resp.message
    finally:
        channel.close()


def refresh(path: str, request_id: str, event_id: str, refresh_command: str, log_path: str, wait: bool):
    channel, stub = with_stub(path)
    try:
        return stub.CodexSessionRefresh(
            pb2.CodexSessionRefreshRequest(
                request_id=request_id,
                event_id=event_id,
                refresh_command=refresh_command,
                log_path=log_path,
                wait=wait,
            ),
            timeout=8,
        )
    finally:
        channel.close()


def status(path: str, request_id: str, log_path: str, wait_seconds: float):
    channel, stub = with_stub(path)
    try:
        return stub.CodexSessionStatus(
            pb2.CodexSessionStatusRequest(
                request_id=request_id,
                log_path=log_path,
                wait_seconds=wait_seconds,
            ),
            timeout=max(2, int(wait_seconds) + 2),
        )
    finally:
        channel.close()


def logs(path: str, request_id: str, lines: int):
    channel, stub = with_stub(path)
    try:
        return stub.CodexSessionLogs(pb2.CodexSessionLogsRequest(request_id=request_id, lines=lines), timeout=5)
    finally:
        channel.close()


def list_runs(path: str, log_path: str):
    channel, stub = with_stub(path)
    try:
        return stub.CodexSessionList(pb2.CodexSessionListRequest(log_path=log_path), timeout=5)
    finally:
        channel.close()


def parse_rows_json(rows_json: str):
    if not rows_json:
        return []
    try:
        return json.loads(rows_json)
    except json.JSONDecodeError:
        return []
