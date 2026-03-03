# Memory V0 Tracker

## Status Legend
- `todo`
- `in_progress`
- `blocked`
- `done`

## Work Items

| ID | Item | Status | Notes |
|---|---|---|---|
| A1 | Cross-repo analysis document | done | `cross_repo_analysis.md` |
| A2 | Dependency analysis document | done | `dependency_analysis.md` |
| A3 | Gap analysis document | done | `gap_analysis.md` |
| M1 | Add minimal schema pack under `src/spawn/ssot/schemas/` | done | seeded with schema index + memory schema |
| M2 | Implement schema registry (`ssot/registry.py`) | done | local `$ref` resolution implemented |
| M3 | Implement `spawnctl ssot list` | done | lists registry descriptors |
| M4 | Implement `spawnctl ssot validate-file` | done | returns machine-readable validation errors |
| M5 | Implement `spawnctl ssot validate-json --stdin` | done | stdin JSON validation path |
| M6 | Enforce pre-dispatch validation | done | event + work.queue validated before dispatch |
| M7 | Enforce worker-start validation | done | transient worker validates work.queue payload |
| M8 | Enforce post-result validation | done | task.result rows validated before append |
| M9 | Cursor model `(path,inode,offset,last_event_id)` | done | persisted per session file in cursor state |
| M10 | Memory extractor v0 (rule-based) | done | evidence-bearing candidate extraction |
| M11 | Gate policy v0 (kind thresholds) | done | auto-accept limited to safe kinds + confidence |
| M12 | SSOT stream `memory.events.jsonl` | done | append-only event log under XDG state |
| M13 | Snapshot rebuild (`accepted/proposals/prompt`) | done | deterministic replay + prompt rendering |
| M14 | Memory CLI (`list/proposals/accept/reject/deprecate`) | done | operator review loop added |
| M15 | `spawnctl memory render` | done | deterministic prompt output |
| M16 | `spawnctl memory rebuild` | done | full replay from SSOT |
| M17 | CI schema gates | todo | block on invalid or drift |
| M18 | Contract fixture tests | todo | replay + compatibility |

## Risks / Blocks
- `M17`: CI pipeline for schema validation and drift checks still pending.
- `M18`: integration fixtures for replay/idempotency are still pending.

## Decision Log
- `2026-03-02`: JSON Schema is canonical for persisted SSOT artifacts.
- `2026-03-02`: Proto3 is canonical for control-plane RPC only.
- `2026-03-02`: OpenAPI 3.1 is derived (catalog/docs) for current scope.
- `2026-03-02`: Cross-repo execution sequencing captured in `plan.md` (Wave 0..5).
