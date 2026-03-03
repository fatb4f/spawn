# Dependency Analysis (Memory V0)

## Dependency Graph Summary

## Hard dependencies (must exist for V0)
- Runtime Python packages in `spawn/pyproject.toml`:
  - `grpcio`, `protobuf` (control-plane transport),
  - `pydantic` (typed contracts),
  - `typer`, `rich` (CLI UX),
  - `jsonschema` (SSOT validation substrate),
  - `xdg-base-dirs`, `dataconfy` (path/config handling).
- System binaries:
  - `systemd-run`, `systemctl`, `journalctl`,
  - `pgrep` (used by codex event source),
  - `codex-refresh-context` (action command).
- File-system inputs:
  - `~/.config/codex/sessions/*.jsonl`,
  - `~/.local/state/codex/meta/*`.

## Soft dependencies (recommended)
- `codex-dome` schema examples for migration seed.
- `fabric-docs` as policy baseline.

## Build/Generation dependencies
- `grpcio-tools` (transient via `uv run --with grpcio-tools` in `scripts/gen.sh`).
- Local generation scripts:
  - `scripts/gen_grpc.py`,
  - `scripts/export_schemas.py`,
  - `scripts/derive_openapi.py`.

## Runtime Control dependencies (systemd)
- `dotfiles/units/user/spawnd-codex-session-refresh.service`
- `dotfiles/units/user/spawn-api.service`
- `dotfiles/presets/user/90-_404.preset`

## Contract dependencies

## Current canonical inputs in `spawn`
- `api/proto/spawn/v1/spawn_control.proto`
- `src/spawn/contracts/models.py`

## Current derived artifacts
- `src/spawn/v1/*_pb2*.py`
- `api/openapi/schemas/*.schema.json`
- `api/openapi/openapi.yaml`
- `api/openapi/tool_ssot.json`

## Memory canonical inputs
- `src/spawn/ssot/schemas/schema.index.json`
- `src/spawn/ssot/schemas/*.schema.json` (minimal memory-oriented subset)

## Dependency Risk Areas

1. Path drift between code and dotfiles config
- Mitigated by generated defaults (`spawnctl daemon write-config`) and updated default source command.

2. Unit dependency drift
- Mitigated by removing missing `spawn.socket` dependency from `spawn-api.service`.

3. Contract authority split
- Current authority is Pydantic model files, but memory plan requires JSON Schema SSOT.

4. Toolchain drift
- No CI workflow currently enforces `scripts/check_gen.sh` on PRs.

## Dependency Actions (Required)
- Introduce `src/spawn/ssot/schemas` and make it authoritative for persisted artifacts.
- Add CI gate for generation and schema validation.
