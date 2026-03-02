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

## XDG links
Create local repo symlinks to runtime config/data:

```bash
cd ~/src/spawn
./scripts/link_xdg_paths.sh
```

## Documentation
Shared standards and architecture live in `fabric-docs`.
