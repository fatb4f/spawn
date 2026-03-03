"""gRPC control plane server over Unix domain socket."""

from __future__ import annotations

import json
import logging
import os
from concurrent import futures
from pathlib import Path

import grpc

from spawn.runtime import codex_session_ops
from spawn.v1 import spawn_control_pb2 as pb2
from spawn.v1 import spawn_control_pb2_grpc as pb2_grpc

logger = logging.getLogger(__name__)


def default_socket_path() -> Path:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    return runtime / "spawn" / "spawn.sock"


def grpc_target_from_path(path: Path) -> str:
    return f"unix://{path}"


class SpawnControlService(pb2_grpc.SpawnControlServicer):
    def Health(self, request: pb2.HealthRequest, context: grpc.ServicerContext) -> pb2.HealthResponse:
        return pb2.HealthResponse(ok=True, message="ok")

    def CodexSessionRefresh(
        self, request: pb2.CodexSessionRefreshRequest, context: grpc.ServicerContext
    ) -> pb2.CodexSessionRefreshResponse:
        log_path = Path(request.log_path).expanduser() if request.log_path else codex_session_ops.default_log_path()
        rc, out, err, rid = codex_session_ops.dispatch_refresh(
            request_id=request.request_id or None,
            event_id=request.event_id or None,
            refresh_command=request.refresh_command or "codex-refresh-context --wait-session-write",
            log_path=log_path,
        )
        return pb2.CodexSessionRefreshResponse(
            ok=rc == 0,
            request_id=rid,
            message=(err or out),
            return_code=rc,
        )

    def CodexSessionStatus(
        self, request: pb2.CodexSessionStatusRequest, context: grpc.ServicerContext
    ) -> pb2.CodexSessionStatusResponse:
        log_path = Path(request.log_path).expanduser() if request.log_path else codex_session_ops.default_log_path()
        rid = codex_session_ops.resolve_request_id(request.request_id, log_path)
        if not rid:
            return pb2.CodexSessionStatusResponse(ok=False, message="no request_id available")
        row = codex_session_ops.status_row(rid, log_path, request.wait_seconds or 2.0)
        if row is None:
            return pb2.CodexSessionStatusResponse(ok=False, request_id=rid, message="request not found")
        return pb2.CodexSessionStatusResponse(ok=True, request_id=rid, row_json=json.dumps(row, sort_keys=True))

    def CodexSessionLogs(self, request: pb2.CodexSessionLogsRequest, context: grpc.ServicerContext) -> pb2.CodexSessionLogsResponse:
        log_path = codex_session_ops.default_log_path()
        rid = codex_session_ops.resolve_request_id(request.request_id, log_path)
        if not rid:
            return pb2.CodexSessionLogsResponse(ok=False, message="no request_id available")
        rc, out, err = codex_session_ops.read_journal_logs(rid, request.lines or 100)
        return pb2.CodexSessionLogsResponse(ok=rc == 0, request_id=rid, logs=out, return_code=rc, message=err)

    def CodexSessionList(self, request: pb2.CodexSessionListRequest, context: grpc.ServicerContext) -> pb2.CodexSessionListResponse:
        log_path = Path(request.log_path).expanduser() if request.log_path else codex_session_ops.default_log_path()
        rows = codex_session_ops.list_rows(log_path)
        return pb2.CodexSessionListResponse(ok=True, rows_json=json.dumps(rows, sort_keys=True))


def serve(socket_path: Path) -> int:
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        socket_path.unlink()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pb2_grpc.add_SpawnControlServicer_to_server(SpawnControlService(), server)
    server.add_insecure_port(grpc_target_from_path(socket_path))
    logger.info("grpc server listening", extra={"socket_path": str(socket_path)})
    server.start()
    server.wait_for_termination()
    return 0
