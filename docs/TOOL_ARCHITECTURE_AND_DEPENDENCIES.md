# Spawn Tool Architecture and Dependency Spec

## Purpose
Define the stable architecture, boundaries, and dependency policy for `spawn` so implementation stays consistent as we evolve from Python proto to Rust LTS.

## Scope
- Daemon: `spawnd`
- CLI: `spawnctl`
- Contracts: event/action schemas + gRPC proto
- Runtime substrate: systemd user services and transient units

## Architecture

### 1) Planes
- Control plane:
  - `spawnctl` invokes daemon RPC over Unix socket.
  - RPC contract source: `api/proto/spawn/v1/spawn_control.proto`.
- Data plane:
  - Event envelopes, action requests/results.
  - Contract source: `src/spawn/contracts/models.py`.
  - Generated JSON Schemas: `api/openapi/schemas/*.schema.json`.
- Runtime plane:
  - systemd unit lifecycle, journald, transient execution.
  - Spawn owns routing/idempotency/audit policy.

### 2) Layering
- `core`:
  - schema and contract construction/validation
  - event taxonomy/namespaces
  - deterministic routing decisions
- `adapters`:
  - gRPC server/client
  - systemd command integration (`systemctl`, `systemd-run`)
  - filesystem/log I/O
- `interface`:
  - `spawnctl` command UX and machine-readable output

### 3) Namespace model (current)
- `codex.session.*`
- `codex.session.meta.*`
- `codex.session.resume.*`
- `codex.session.service.*`
- `codex.config.*`

## Contract and Generation Policy

### Canonical inputs
- `api/proto/spawn/v1/spawn_control.proto`
- `src/spawn/contracts/models.py`

### Derived artifacts
- `src/spawn/v1/spawn_control_pb2.py`
- `src/spawn/v1/spawn_control_pb2_grpc.py`
- `api/openapi/schemas/*.schema.json`
- `api/openapi/openapi.yaml`
- `api/openapi/tool_ssot.json` (validated against `ToolSsotV1.schema.json`)

### Commands
- `./scripts/gen.sh`: regenerate all derived artifacts.
- `./scripts/check_gen.sh`: fail if generated artifacts are out of date.

### Rule
- Never hand-edit generated files.
- Changes to contracts must be additive unless explicitly version-bumped.

### Thin-client model
- Generated thin clients:
  - `src/spawn/v1/spawn_control_pb2.py`
  - `src/spawn/v1/spawn_control_pb2_grpc.py`
- Hand-authored transport adapter:
  - `src/spawn/adapters/grpc_client.py`
- Rule:
  - generated stubs own wire types and RPC method shape
  - adapter/CLI own retries, timeouts, and operator UX

## Dependency Policy

### Runtime dependencies (allowed)
- `grpcio`
- `pydantic`
- `dataconfy`
- `xdg-base-dirs`
- `protobuf`

### Build-time tools (generation only)
- `grpcio-tools` (used transiently via `uv run --with grpcio-tools`)

### Disallowed patterns
- hidden runtime deps added only for local scripts
- duplicate wrappers that bypass package entrypoints
- direct dependence on generated artifacts as authoring source

## Systemd Expectations
- Service entrypoints run through packaged commands (`spawnctl`, `spawnd`).
- Runtime paths are XDG-aware.
- Transient execution uses `systemd-run` with explicit unit naming and captured logs.
- Daemon and CLI contracts remain stable across implementation changes.

## Migration Locks (Python -> Rust)
- Freeze before Rust cutover:
  - RPC proto schema
  - event/action schema fields and semantics
  - namespace taxonomy
  - on-disk JSONL and artifact layout
- Maintain cross-implementation integration tests against the same contract fixtures.
