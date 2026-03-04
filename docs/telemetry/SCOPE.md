# Telemetry Forwarding Scope (Baseline)

## Objective

Establish a reliable telemetry transport path for Codex OTel logs:

`codex-cli (OTLP/HTTP logs) -> local OpenTelemetry Collector -> OTLP backend`

This phase is transport-only and should produce a reproducible baseline.

## In Scope

- Run OpenTelemetry Collector as a managed `systemd --user` service.
- Configure Codex launch to emit OTLP log telemetry to the local collector.
- Forward telemetry from collector to a backend (Langfuse-compatible OTLP endpoint).
- Capture transport reliability signals (uptime, restarts, drops, retries, latency).

## Out of Scope

- Context generation or prompt-refresh optimization.
- SSOT/event-schema normalization in `spawn`.
- Memory derivation, gate logic, or policy actions.
- PTY capture or full terminal stream recording.
- Spawn-originated telemetry ingestion (until Codex baseline is stable).

## Baseline Acceptance Criteria

### Observation window

- Full gate: 60 minutes minimum.
- Accelerated gate: 10 Codex command runs for smoke validation while wiring assets.

### Health definition (collector)

- `otel-collector.service` is `active (running)` for the full window.
- Restart count: `<= 1` during normal operation (excluding intentional failure drills).
- Health endpoint is reachable (if configured).

### Transport success definition

- Codex OTel logs are visible in backend within 60s from command execution.
- Resource attributes include `service.name=codex-cli`.
- Exporter failures/retries are either below threshold or explicitly characterized in runbook output.

### Failure characterization definition

For each drill (DNS failure, auth failure, backend outage), capture:

- journal signature(s)
- retry/backoff behavior
- recovery behavior (auto vs manual)
- whether drops occurred (or queue preserved data)

### Go/No-Go decision

A full go/no-go decision requires full-gate window + failure characterization.
An accelerated go/no-go can be used for implementation packet closure only.

## Control Principle

Transport-only phase must not change control-plane behavior.  
`spawn` remains the control/audit authority while telemetry transport is validated.

## Runtime policy notes

- Collector runs under `systemd --user` with explicit reliability directives.
- Linger policy must be explicit:
  - either `loginctl enable-linger <user>` is required for baseline,
  - or baseline is scoped to active logged-in sessions only.
