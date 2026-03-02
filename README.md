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

## Run
```bash
cd ~/src/spawn
./bin/spawnd codex-session-refresh
```

## Documentation
Shared standards and architecture live in `fabric-docs`.
