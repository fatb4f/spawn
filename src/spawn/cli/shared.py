"""Shared CLI helpers."""

from __future__ import annotations

from pathlib import Path

import grpc
from rich.console import Console

from spawn.adapters.grpc_server import default_socket_path, grpc_target_from_path
from spawn.v1 import spawn_control_pb2_grpc as pb2_grpc

console = Console()


def socket_path(value: str) -> Path:
    return Path(value).expanduser() if value else default_socket_path()


def channel_and_stub(path_value: str):
    target = grpc_target_from_path(socket_path(path_value))
    channel = grpc.insecure_channel(target)
    return channel, pb2_grpc.SpawnControlStub(channel)

