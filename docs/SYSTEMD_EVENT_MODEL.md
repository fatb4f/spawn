# Spawn Systemd Event Model

## Goal
Make `spawn` systemd-first:
- systemd provides activation, scheduling, isolation, resources, and lifecycle.
- `spawnd` provides contracts, routing, idempotency, and audit policy.

## Planes

### Control plane
- `spawnctl` <-> `spawnd` over Unix domain socket gRPC.
- API contract: `api/proto/spawn/v1/spawn_control.proto`.
- Runtime API server currently binds `%t/spawn/spawn.sock`.
- Full `spawn.socket` activation remains a follow-up.

### Data plane
- `.path` and `.timer` units trigger ingest/dispatch/reconcile flows.
- Heavy actions run as transient units with `systemd-run` under `spawn.slice`.

## Contracts (SSOT)

### `event_envelope_v1`
```json
{
  "schema": "event_envelope_v1",
  "event_id": "uuid",
  "event_type": "codex.session.started",
  "source": "path:codex-meta-prompt",
  "observed_at": "2026-03-02T17:00:00Z",
  "dedupe_key": "codex.session.started:session_id",
  "payload": {}
}
```

### `action_request_v1`
```json
{
  "schema": "action_request_v1",
  "request_id": "uuid",
  "event_id": "uuid",
  "action": "codex.refresh_context",
  "policy": {
    "timeout_sec": 30,
    "retry": "none",
    "execution_class": "transient"
  },
  "args": []
}
```

### `action_result_v1`
```json
{
  "schema": "action_result_v1",
  "request_id": "uuid",
  "event_id": "uuid",
  "status": "ok",
  "return_code": 0,
  "started_at": "2026-03-02T17:00:01Z",
  "finished_at": "2026-03-02T17:00:02Z",
  "artifacts": {
    "stdout": "...",
    "stderr": "..."
  }
}
```

## State layout
- Inbox: `%t/spawn/inbox/` (`RuntimeDirectory=spawn`)
- Dedupe cache: `%S/spawn/dedupe/` (`StateDirectory=spawn`)
- Audit log: `%S/spawn/audit.jsonl`
- Evidence: `%S/spawn/runs/<request_id>/`

## Unit inventory (initial)

### `spawn.socket`
- `ListenStream=%t/spawn/spawn.sock`
- `SocketMode=0660`
- Planned for activation routing; current API service binds this path directly.

### `spawnd.service`
- `Type=notify` only after `sd_notify` is implemented; otherwise `Type=simple`
- Reads config from `%h/.config/spawn/spawnd.toml` (user mode)
- Uses `RuntimeDirectory=spawn`, `StateDirectory=spawn`, `CacheDirectory=spawn`

### `spawn-dispatch.path`
- Watches `%t/spawn/inbox`
- `DirectoryNotEmpty=` trigger
- Activates `spawn-dispatch.service`

### `spawn-dispatch.service`
- Oneshot drain of inbox files
- Validate -> dedupe -> route -> emit action requests
- For transient actions: call `systemd-run --user --collect ...`

### `spawn-reconcile.timer` + `spawn-reconcile.service`
- Periodic invariant check and replay of incomplete runs
- `Persistent=true`

## Idempotency and ordering
- Dedupe key required in every `event_envelope_v1`.
- Keep dedupe TTL per event class (default 24h).
- Ordering policy:
  - per dedupe key: serialized
  - across keys: bounded parallelism
- Backpressure:
  - max inbox drain batch size
  - max concurrent transient units

## Transient execution profile
Use action-class defaults when launching transient units:
- `Slice=spawn.slice`
- `NoNewPrivileges=yes`
- `PrivateTmp=yes`
- `MemoryMax=` and `CPUQuota=` by action class
- Capture stdout/stderr into `%S/spawn/runs/<request_id>/`

## Logging and audit
- Journald: operational logs and unit lifecycle.
- JSONL audit: canonical action/event ledger (append-only).
- Required correlation fields in both channels:
  - `event_id`, `request_id`, `action`, `status`.

## Failure policy
- Invalid event: reject + audit entry.
- Duplicate event: skip + audit entry.
- Transient action failure: policy-driven retry or escalate.
- Escalation target: emit `spawn.action.failed` event and optional `OnFailure=` unit.

## Security baseline
- Socket ACL policy (`0660`, dedicated group) for CLI access.
- Validate all external input before routing.
- Keep secrets in systemd credentials, not env/config.

## Migration locks (Python -> Rust)
Freeze before daemon replacement:
- IPC protocol and error schema
- event/action schema versions
- on-disk state/audit locations and formats
- CLI command/exit-code contract

## Immediate implementation sequence
1. Add schema models and validation for event/action/result.
2. Add inbox dispatcher service + path unit.
3. Move heavy actions to transient `systemd-run` execution.
4. Add reconcile timer/service.
5. Add socket activation for control API.
