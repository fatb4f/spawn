# SSOT Schema Registry

- Registry: `schema.index`
- Version: `v1`

## Schemas

| Name | Version | Canonical | Title | Description | File |
| --- | --- | --- | --- | --- | --- |
| `event.envelope` | `v1` | yes | event.envelope | Canonical envelope for all persisted spawn events crossing systemd unit boundaries. | `event.envelope.schema.json` |
| `evidence.bundle.telemetry` | `v1` | yes | evidence.bundle.telemetry | Telemetry bundle linking traces, scalar signals, and optional artifact references. | `evidence.bundle.telemetry.schema.json` |
| `evidence.capsule` | `v1` | yes | evidence.capsule | Evidence capsule combining trace correlation, signals, and immutable artifact pointers. | `evidence.capsule.schema.json` |
| `reason.codes` | `v1` | yes | reason.codes | Registry payload defining normalized reason code taxonomy used by decisions. | `reason.codes.schema.json` |
| `work.queue` | `v1` | yes | work.queue | Queue payload describing runnable tasks, dependencies, and execution budget hints. | `work.queue.schema.json` |
| `task.result` | `v1` | yes | task.result | Execution result emitted by workers and dispatchers for each task. | `task.result.schema.json` |
| `gate.decision` | `v1` | yes | gate.decision | Decision emitted by gate evaluation before promotion and action execution. | `gate.decision.schema.json` |
| `promotion.decision` | `v1` | yes | promotion.decision | Promotion decision that gates whether a run result can advance beyond review. | `promotion.decision.schema.json` |
| `run.manifest` | `v1` | yes | run.manifest | Reproducibility manifest for one run, including inputs, commands, artifacts, and runtime metadata. | `run.manifest.schema.json` |
| `state.space` | `v1` | yes | state.space | State-space snapshot container used for memory, preferences, and work-item context. | `state.space.schema.json` |
| `memory` | `v1` | yes | memory | Canonical memory state snapshot derived from the append-only memory event stream. | `memory.schema.json` |
| `memory.cursor` | `v1` | yes | memory.cursor | Per-source cursor checkpoints for deterministic incremental memory ingestion. | `memory.cursor.schema.json` |
| `memory.accepted` | `v1` | yes | memory.accepted | Snapshot of accepted memory items derived from append-only memory events. | `memory.accepted.schema.json` |
| `memory.proposals` | `v1` | yes | memory.proposals | Snapshot of pending and reviewed memory proposals. | `memory.proposals.schema.json` |
| `memory.patch` | `v1` | yes | memory.patch | Patch payload for accepted memory upserts and deprecations. | `memory.patch.schema.json` |
| `memory.proposal` | `v1` | yes | memory.proposal | Proposal payload wrapper emitted when auto-accept policy does not apply. | `memory.proposal.schema.json` |
| `memory.proposal.decision` | `v1` | yes | memory.proposal.decision | Review decision payload for accepting or rejecting a pending memory proposal. | `memory.proposal.decision.schema.json` |
