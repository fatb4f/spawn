# Telemetry Asset Matrix

| Asset | Location | Owner | Current State | Desired State | Gap |
| --- | --- | --- | --- | --- | --- |
| Codex binary | `/usr/bin/codex` | Runtime | Installed and active for local + SSH runs | Same | None |
| Codex emitter contract | `spawn/docs/telemetry/EMITTER_CONTRACT.md` | Spawn/Ops | Pinned to `[otel]` + `otlp-http` logs (`/v1/logs`) | Stable documented contract | Closed |
| Codex config | `dotfiles/config/codex/config.toml` | Dotfiles | `[otel]` section present with local collector endpoint | Keep in sync with launch policy | Closed |
| Codex shell wrapper | `dotfiles/config/fish/functions/codex.fish` | Dotfiles | Loads canonical env file before launch | Keep parity with other launch paths | Closed |
| VSCode codex launcher | `dotfiles/local/bin/codex-vscode` | Dotfiles | Loads canonical env file before launch | Keep parity with shell + desktop | Closed |
| Codex ACP bridge unit | `dotfiles/units/user/codex-acp.service` | Dotfiles | Includes `EnvironmentFile=-%h/.config/codex/otel.env` | Keep parity for ACP path | Closed |
| Collector distribution/version | `dotfiles/local/bin/otelcol-contrib-install` | Ops/Dotfiles | Installer script pins `otelcol-contrib` `0.147.0` | Maintain pinned version policy | Closed |
| Collector runtime binary | `~/.local/bin/otelcol-contrib` | Ops | Installed (`0.147.0`) | Keep managed via installer script | Closed |
| OTLP receiver protocol/ports | `dotfiles/config/otelcol/collector.yaml` | Ops | Receiver pinned to OTLP HTTP on `127.0.0.1:4318` | Same | Closed |
| Collector health endpoint | `dotfiles/config/otelcol/collector.yaml` | Ops | `health_check` extension on `127.0.0.1:13133` | Same | Closed |
| OTEL collector unit | `dotfiles/units/user/otel-collector.service` | Dotfiles/Ops | User service exists with restart/timeouts/hardening | Keep linked in user unit dir | Closed |
| OTEL collector config | `dotfiles/config/otelcol/collector.yaml` | Dotfiles/Ops | Versioned config in repo | Same | Closed |
| Canonical OTEL env contract | `dotfiles/config/codex/otel.env` | Dotfiles/Ops | Single env file used by wrappers + units | Same | Closed |
| Backend endpoint contract | `dotfiles/config/codex/otel.env` | Ops | Default local mock backend `http://127.0.0.1:4320` with override model | Replace with real backend in production | Open (ops decision) |
| Backend auth header contract | `dotfiles/config/codex/otel.env` | Ops/Security | `OTEL_BACKEND_AUTHORIZATION` variable defined | Move to systemd credentials in next phase | Open (next phase) |
| Debug exporter path | `dotfiles/config/otelcol/collector.yaml` | Ops | `debug` exporter enabled for baseline visibility | Optional profile split later | Closed |
| Transport validation checklist | `spawn/docs/telemetry/RUNBOOK.md` | Spawn/Ops | Runbook exists and has baseline/failure drills | Keep current with implementation | Closed |
| Baseline execution tracker | `spawn/docs/telemetry/TRACKER.md` | Spawn/Ops | WP0-WP5 status tracking in repo | Keep current with each run | Closed |

## Live Unit Snapshot (2026-03-04)

Relevant user unit files currently linked:

- `spawnd-codex-session-refresh.path`
- `spawnd-codex-session-refresh.service`
- `spawn-api.service`
- `codex-acp.service`
- `otel-collector.service` (linked, currently inactive by default)

## Launch-path Parity

Codex launch paths aligned to one env contract:

- terminal wrapper (`fish`): `config/fish/functions/codex.fish`
- VSCode launcher: `local/bin/codex-vscode`
- ACP unit path: `units/user/codex-acp.service`
