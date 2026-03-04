# Telemetry Baseline Implementation Plan

## Objective

Implement a reproducible, transport-only telemetry baseline:

`codex-cli -> local OpenTelemetry Collector -> OTLP backend`

This plan operationalizes `SCOPE.md`, `ASSET_MATRIX.md`, `ANALYSIS.md`, and `RUNBOOK.md`.

## Scope Guard

- In scope: emitter contract, collector service/config, launch-path parity, transport validation.
- Out of scope: spawn memory/SSOT ingestion changes, context refresh logic, policy automation.

## Work Packages

### WP0 - Freeze Contracts (blocking)

Targets: `E1`, `E2` from `ANALYSIS.md`.

- Pin Codex emitter contract:
  - exact Codex command
  - exact env vars
  - exact feature toggle path (if required)
- Pin protocol:
  - OTLP/gRPC (`4317`) or OTLP/HTTP (`4318`)
  - receiver/exporter path must match

Exit criteria:
- One command emits telemetry locally with deterministic settings.
- Protocol choice documented in repo and reused by all assets.

### WP1 - Add Repo Assets (G1/G2)

Targets: collector unit + config + env contract.

- Add collector config under version control (spawn or dotfiles-managed path).
- Add `otel-collector.service` user unit with:
  - `Restart=on-failure`
  - `RestartSec=2`
  - `StartLimitBurst` + `StartLimitIntervalSec`
  - explicit `ExecStart=... --config ...`
  - journald logging
- Add canonical OTEL env file contract consumed by all Codex launch paths.

Exit criteria:
- Unit + config + env files exist in repo and are deployable without manual edits.

### WP2 - Launch Path Parity (G3)

Targets: terminal, VSCode, any direct systemd Codex path.

- Ensure all Codex launchers consume the same OTEL environment contract.
- Remove per-launcher telemetry drift (ad hoc overrides unless explicitly documented).
- Document whether `codex-acp.service` is in scope as a Codex runtime path.

Exit criteria:
- Same telemetry attributes and backend target from each supported launch path.

### WP3 - Host Bring-Up + Baseline Window (G4)

Targets: runbook execution and objective measurements.

- Deploy assets.
- Run runbook sections A-D (`RUNBOOK.md`):
  - service bring-up
  - traffic check
  - backend receipt
  - 60-minute observation window
- Capture artifacts:
  - collector logs
  - restart count
  - backend evidence

Exit criteria:
- Baseline acceptance criteria from `SCOPE.md` pass.

### WP4 - Failure Characterization

Targets: deterministic failure behavior for transport layer.

- Execute runbook section E drills:
  - DNS failure
  - auth failure
  - backend unreachable
- For each drill capture:
  - log signatures
  - retry/backoff behavior
  - recovery mode
  - drop/queue evidence

Exit criteria:
- All drills have documented outcomes and remediation notes.

### WP5 - Decision Gate + Handoff

- Record go/no-go decision.
- If go:
  - mark telemetry baseline as stable
  - open next packet for spawn-side telemetry ingestion (separate scope)
- If no-go:
  - list hard blockers with owner/action/date

Exit criteria:
- Signed baseline summary with explicit next phase trigger.

## Task Matrix

| ID | Item | Maps To | Owner | Status |
| --- | --- | --- | --- | --- |
| T1 | Pin Codex emitter contract | E1 | Ops | TODO |
| T2 | Pin OTLP protocol | E2 | Ops | TODO |
| T3 | Add collector unit | G1 | Ops/Dotfiles | TODO |
| T4 | Add collector config | G2 | Spawn/Ops | TODO |
| T5 | Add canonical OTEL env contract | G3 | Dotfiles/Ops | TODO |
| T6 | Enforce launch-path parity | G3 | Dotfiles/Ops | TODO |
| T7 | Run baseline observation window | G4 | Ops | TODO |
| T8 | Run failure drills + evidence capture | G4 | Ops | TODO |
| T9 | Publish go/no-go summary | Gate | Ops | TODO |

## Definition of Done

- All `SCOPE.md` acceptance criteria pass with evidence.
- `RUNBOOK.md` can be replayed on a clean host setup.
- No unresolved ambiguity on emitter settings, protocol, or launch-path env contract.

## Rollback Criteria

Rollback to pre-baseline state if:

- collector enters sustained restart loop,
- telemetry path causes Codex launch regressions,
- backend auth or protocol remains unresolved after WP2.

Rollback action:
- disable collector unit, remove OTEL env overrides from launchers, keep docs and captured failure evidence.
