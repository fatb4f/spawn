# Detailed Analysis: Codex Telemetry Forwarding Baseline

## 1) Current State Summary

- Codex OTel emitter contract is now pinned to `[otel]` + `otlp-http` (`/v1/logs`).
- Local collector service/assets are wired in dotfiles:
  - `dotfiles/units/user/otel-collector.service`
  - `dotfiles/config/otelcol/collector.yaml`
  - `dotfiles/config/codex/otel.env`
- Launch-path parity is implemented across shell wrapper, VSCode launcher, and ACP unit env.
- Baseline evidence artifacts are captured under `spawn/docs/telemetry/artifacts/`.

## 2) Dependency Analysis

### Hard dependencies

1. Codex emitter contract (`[otel]` config, local receiver endpoint).
2. Collector binary (`otelcol-contrib` pinned at `0.147.0`).
3. Managed user unit lifecycle (`systemd --user` service).
4. Backend endpoint/auth variables (local mock or real backend).

### Soft dependencies

- systemd credentials migration for backend auth.
- spawn-side ingestion/normalization (next phase).
- dashboard/alerts automation.

## 3) Gap Analysis (Post-Execution)

### Closed

- G1: collector service substrate.
- G2: collector pipeline config in repo.
- G3: codex emitter + launch-path parity contract.
- G4: transport runbook and execution artifacts.

### Remaining

- Production backend endpoint + credential policy is still an ops decision.
- Full 60-minute observation window is not yet executed; current run is an accelerated baseline pass.

## 4) Risk Analysis

| Risk | Status | Notes |
| --- | --- | --- |
| Codex emits no OTel payloads | Mitigated | E1 proved local OTLP/HTTP log emission to `/v1/logs`. |
| Launch-path drift | Mitigated | Wrapper + VSCode + ACP now consume common env contract. |
| Collector restart loops | Partially mitigated | Service policy added; rapid failure drills can hit StartLimit and require `reset-failed`. |
| Backend transport failures are opaque | Mitigated | DNS/auth/outage signatures captured in failure drills. |
| Scope creep into spawn SSOT/memory | Mitigated | No memory/control-plane changes in this packet. |

## 5) Execution Outcome by Gate

### E1: Codex emits OTLP locally

- PASS. Receiver observed protobuf POSTs to `/v1/logs` from Codex execution.

### E2: Protocol pinned

- PASS. Baseline pinned to `otlp-http`.

### G1/G2: Collector substrate + config

- PASS. Unit/config/env assets added and deployed.

### G3: Launch parity

- PASS. Verified telemetry emission through `codex-vscode` and fish `codex` wrapper path.

### G4: Runbook + failure characterization

- PASS (accelerated). Baseline traffic run executed; DNS/auth/outage drills captured.
- NOTE: Full 60-minute window remains pending for strict long-window validation.

## 6) Recommended Next Actions

1. Replace local mock backend endpoint with production OTLP endpoint + secret handling via credentials.
2. Run one strict 60-minute validation window and append the evidence packet.
3. Move to next phase only after backend auth/endpoint policy is finalized.
