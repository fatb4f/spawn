# spawn

Spawn fabric runtime repository.

## Scope
- `spawnd`: daemon runtime substrate
- `spawnctl`: thin orchestration/operator client

## Implemented
- `bin/spawnd codex-session-refresh`
  - consumes events from `codex-event-source`
  - triggers `codex-refresh-context --wait-session-write` for:
    - `codex.session.started`
    - `codex.session.ended`
  - writes JSONL execution rows to:
    - `~/.local/state/codex/spawn/spawnd-codex-session-refresh.jsonl`

- codex helpers owned by spawn:
  - `bin/codex-event-source`
  - `bin/codex-config-validate`
  - `bin/codex-resume-diagnose`
  - `bin/codex-alert-log`
  - `bin/codex-session-events`

## Run
```bash
cd ~/src/spawn
./bin/spawnd codex-session-refresh
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
- `proto/spawn/v1/spawn_control.proto`

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
