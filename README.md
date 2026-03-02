# spawn

Spawn fabric runtime repository.

## Scope
- `spawnd`: daemon runtime substrate
- `spawnctl`: thin orchestration/operator client
- contracts: spec-first event/action schemas under `api/` + `proto/`

## Source Layout
- `src/spawn/cli.py`
- `src/spawn/core/service.py`
- `src/spawn/contracts/*`
- `src/spawn/runtime/*`
- `src/spawn/adapters/*`

## Namespaces (current)
- `codex.session.*`
- `codex.session.meta.*`
- `codex.session.resume.*`
- `codex.session.service.*`
- `codex.config.*`

## Run
```bash
cd ~/src/spawn
spawnctl daemon serve-api
```

## Install (packaged)
```bash
cd ~/src/spawn
uv pip install --system -e .
```

Installed console commands:
- `spawnd`
- `spawnctl`

Package source lives under `src/spawn/`.

## Control API (gRPC over Unix socket)
- Start API server:
  - `spawnctl daemon serve-api --socket-path /run/user/$UID/spawn/spawn.sock`
- Health check:
  - `spawnctl daemon health --json`
- Codex session actions (RPC client):
  - `spawnctl codex-session refresh`
  - `spawnctl codex-session status --request-id <id>`
  - `spawnctl codex-session logs --request-id <id>`
  - `spawnctl codex-session list`

Proto contract:
- `api/proto/spawn/v1/spawn_control.proto`

## Spec-first workflow (as in spec-hydra)
- regenerate derived schemas:
  - `./scripts/gen.sh`
- verify generated artifacts are committed:
  - `./scripts/check_gen.sh`

Canonical contract inputs:
- `api/proto/spawn/v1/spawn_control.proto`
- `src/spawn/contracts/models.py`

Derived artifacts:
- `api/openapi/openapi.yaml`
- `api/openapi/schemas/*.schema.json`
- `src/spawn/v1/*_pb2*.py`

## Optional dependencies
- `xdg-base-dirs` (`python-xdg-base-dirs`) for strict XDG path resolution.
- `pydantic` for typed config validation.
- `dataconfy` for YAML/JSON config loading with env support.

`spawnd.toml` remains the default config format. Use `.yaml`/`.json` to activate
`dataconfy` loading.

## XDG links
Create local repo symlinks to runtime config/data:

```bash
cd ~/src/spawn
./scripts/link_xdg_paths.sh
```


## Engineering Rules
This repo follows `fabric-docs/docs/FABRIC_MUST_RULES.md` and `fabric-docs/docs/SYSTEMD_DIRECTIVE_GUIDELINES.md` as mandatory architecture constraints.

## Documentation
Shared standards and architecture live in `fabric-docs`.
