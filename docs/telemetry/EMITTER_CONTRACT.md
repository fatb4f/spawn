# Codex OTel Emitter Contract

## Purpose

Pin the exact Codex-side contract used for telemetry forwarding baseline.

## Contract (Pinned)

- Signal type: OpenTelemetry **logs** emitted by Codex.
- Protocol: `otlp-http` with protobuf payloads.
- Local collector endpoint: `http://127.0.0.1:4318/v1/logs`.
- Config source: `~/.config/codex/config.toml` + `~/.config/codex/otel.env`.

## Codex Config Contract

```toml
[otel]
environment = "${CODEX_OTEL_ENVIRONMENT}"
exporter = { otlp-http = { endpoint = "${CODEX_OTEL_ENDPOINT}", protocol = "binary" } }
log_user_prompt = false
```

## Env Contract

```bash
CODEX_OTEL_ENVIRONMENT=dev
CODEX_OTEL_ENDPOINT=http://127.0.0.1:4318/v1/logs
```

## E1 Proof (local receiver)

Validation command (2026-03-04):

```bash
CODEX_HOME=<temp_config_dir_with_otel> codex exec --skip-git-repo-check 'respond with exactly: ok'
```

Observed receiver hits:

- HTTP path: `/v1/logs`
- Content type: `application/x-protobuf`
- Multiple POST batches during one Codex run

This proves Codex emits OTLP HTTP logs with the pinned contract.

## E2 Decision

- Baseline protocol is pinned to `otlp-http` for all WP1-WP5 work.
- `otlp-grpc` is deferred and can be added as a secondary profile later.
