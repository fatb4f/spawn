# Telemetry Execution Tracker

## Status

| WP | Gate | Status | Evidence |
| --- | --- | --- | --- |
| WP0 | E1/E2 | PASS | `EMITTER_CONTRACT.md` (local `/v1/logs` protobuf POSTs observed on 2026-03-04) |
| WP1 | G1/G2 | PASS | dotfiles assets added: `otel-collector.service`, `collector.yaml`, `otel.env`, installer script |
| WP2 | G3 | PASS | parity verified across `codex-vscode` and fish wrapper launch paths |
| WP3 | G4 (A-D) | PASS (accelerated) | `artifacts/baseline_smoke_20260304.md` |
| WP4 | G4 (E) | PASS | DNS/auth/outage drills captured in `artifacts/failure_drills_20260304T180506Z.md` |
| WP5 | Decision | PASS (accelerated go) | `BASELINE_DECISION_2026-03-04.md` |
