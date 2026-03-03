# Memory V0 Analysis

## Objective
Build `agent:memory` as a spec-first subsystem in `spawn`, using codex-session artifacts as ingestion input.

## Scope (V0)
- Ingest codex session deltas.
- Extract memory candidates.
- Gate (auto-accept vs review queue).
- Persist to append-only SSOT.
- Render derived memory context.

## Out of Scope (V0)
- General multi-tool orchestration loops.
- Broad event catalog expansion beyond codex-session + reconciliation.
- HTTP API surface.

## Architectural Boundaries
- JSON Schema SSOT:
  - Canonical for cross-unit persisted artifacts (`src/spawn/ssot/schemas/*`).
  - Applies to inbox events, JSONL audit rows, manifests, memory stores.
- Proto3:
  - Canonical for control-plane RPC only (`spawnctl` <-> `spawnd`).
- OpenAPI 3.1:
  - Derived schema catalog (components/docs), not runtime authority.

## Minimal Contract Set
- `event.envelope`
- `evidence.bundle.telemetry`
- `evidence.capsule`
- `reason.codes`
- `work.queue`
- `task.result`
- `gate.decision`
- `promotion.decision`
- `run.manifest`
- `state.space`
- `memory` (new; accepted/proposals/tombstones)

## Key Invariants
- All persisted rows include `schema_name` and `schema_version`.
- Validation at three boundaries:
  - pre-dispatch,
  - worker-start,
  - post-result.
- SSOT JSONL is authoritative; snapshots are rebuildable caches.
- Idempotency enforced with deterministic IDs + dedupe keys.

## Risks
- Dual contract drift between Pydantic and JSON Schema.
- Duplicate memory entries without deterministic identity rules.
- Cursor corruption on file rotation/truncation.
- Over-eager auto-accept for sensitive memory kinds.

## Mitigations
- Make `src/spawn/ssot/schemas` canonical and generate/validate downstream artifacts.
- Use deterministic `memory_id` / `proposal_id` derivation.
- Cursor tuple: `(path, inode, offset, last_event_id)`.
- Gate thresholds by memory kind + evidence strength.

## Exit Criteria (V0)
- `spawnctl ssot validate` exists and passes in CI.
- Memory ingestion writes schema-valid SSOT events.
- Rebuild from SSOT reproduces snapshots deterministically.
- Operator can list/accept/reject/deprecate memory entries.
