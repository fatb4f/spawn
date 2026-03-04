# Telemetry Baseline Runbook (Transport-Only)

## Purpose

Execute and verify the baseline path:

`codex-cli (OTLP logs) -> local collector -> OTLP backend`

This runbook does not change `spawn` SSOT/control behavior.

## Preconditions

- Codex emitter contract is pinned (Gate E1 passed).
- OTLP protocol is pinned (Gate E2 passed).
- Collector unit/config/env assets are deployed.
- Linger policy is explicit:
  - either `loginctl enable-linger <user>` is enabled,
  - or tests are limited to active login sessions.

## A) Service bring-up checks

```bash
systemctl --user daemon-reload
systemctl --user enable --now otel-collector.service
systemctl --user is-enabled otel-collector.service
systemctl --user is-active otel-collector.service
systemctl --user status --no-pager otel-collector.service
```

Expected:
- enabled + active.
- no immediate restart loop.

## B) Baseline traffic check

Run at least one Codex command through the canonical launch path:

```bash
codex --version
# or canonical resume command for your environment
```

Then verify collector activity:

```bash
journalctl --user -u otel-collector.service -n 200 --no-pager
```

Expected:
- receiver/exporter pipeline activity appears.
- no persistent auth/endpoint failures.

## C) Backend receipt check

Use backend query/dashboard for:

- `service.name=codex-cli`
- recent timeframe (last 5 minutes)

Expected:
- at least one received OTel log batch within 60s of command execution.

## D) Observation window

- Full mode duration: 60 minutes.
- Load: at least 10 Codex commands (or 3 session starts/resumes, whichever is higher).
- Accelerated mode: 10 command runs over a short validation window for implementation smoke checks.

Collect:

```bash
systemctl --user show otel-collector.service -p NRestarts --value
journalctl --user -u otel-collector.service --since "-60 min" --no-pager
```

Record:
- restart count
- error signatures
- retry/backoff patterns
- backend receipt latency

## E) Failure drills (characterization)

Run each drill once and record outcomes.

1. DNS failure simulation
2. Backend auth failure (invalid token/header)
3. Backend outage/unreachable endpoint

For each drill capture:
- collector journal signature
- retry behavior
- recovery mode (automatic/manual)
- data loss evidence (drop vs queue/retry)
- start-limit behavior (`reset-failed` requirement if start bursts are exceeded)

## F) Pass/Fail criteria

Pass when all are true:

- `otel-collector.service` active for full window.
- restarts `<= 1` (excluding deliberate drills).
- Codex OTel logs visible in backend with `service.name=codex-cli`.
- failure drills are documented with deterministic outcomes.

Fail when any are true:

- repeated restart loop/flapping.
- no backend telemetry despite local execution.
- protocol/auth contract remains ambiguous.
- failure behavior not characterized.

## Artifacts to save

- collector journal excerpt (`.log`)
- backend screenshots/queries (or exported references)
- baseline summary markdown with go/no-go decision
