# Telemetry Baseline Decision (2026-03-04)

## Decision

**GO (accelerated baseline)** for moving to the next telemetry packet.

## Basis

- WP0-WP4 passed in accelerated mode.
- Codex emitter contract is pinned and locally verified.
- Collector assets are versioned and deployable via dotfiles.
- Launch-path parity is implemented for shell + VSCode + ACP unit env.
- Failure signatures for DNS/auth/outage are captured and reproducible.

## Evidence

- Emitter contract: `spawn/docs/telemetry/EMITTER_CONTRACT.md`
- Baseline smoke summary: `spawn/docs/telemetry/artifacts/baseline_smoke_20260304.md`
- Failure drills: `spawn/docs/telemetry/artifacts/failure_drills_20260304T180506Z.md`

## Open Conditions

- Full 60-minute observation window remains pending (full gate not yet executed).
- Production backend endpoint and credential source are not finalized.
- `OTEL_BACKEND_AUTHORIZATION` should move to systemd credentials in the next phase.

## Operational Note

`otel-collector.service` is linked but left inactive by default after baseline execution to avoid noisy retries when no backend is running.
