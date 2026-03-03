# Spawn Memory

`spawn` memory is a local, schema-validated capability that turns session activity into durable operator-reviewed memory.

## Purpose
- Persist high-signal facts from session streams.
- Keep memory deterministic, auditable, and replayable.
- Provide a compact rendered context for downstream tools.

## Capability Model
- Input: session deltas and control events.
- Extraction: candidate memories with evidence.
- Gating: auto-accept for safe/high-confidence kinds, otherwise queue for review.
- Persistence: append-only event stream as SSOT.
- Derivation: rebuild accepted/proposed snapshots and rendered prompt context.

## Data Contracts
- Persisted artifacts are governed by JSON Schema under `src/spawn/ssot/schemas/`.
- Validation is enforced at runtime boundaries:
  - pre-dispatch
  - worker-start
  - post-result

## Storage
- SSOT event stream: `memory.events.jsonl`.
- Derived snapshots:
  - accepted memory set
  - proposal queue
  - rendered prompt context
- Directory resolution prefers systemd directories (`STATE_DIRECTORY`/`CACHE_DIRECTORY`) and falls back to XDG paths.

## Operator Interface
- `spawnctl memory list`
- `spawnctl memory proposals`
- `spawnctl memory accept <proposal_id>`
- `spawnctl memory reject <proposal_id>`
- `spawnctl memory deprecate <memory_id>`
- `spawnctl memory render`
- `spawnctl memory rebuild`
- `spawnctl memory ingest`

## Lifecycle Status
- Memory V0 delivery is closed in issue `#1`:
  - https://github.com/fatb4f/spawn/issues/1
