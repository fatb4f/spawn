# Memory V0 Execution Plan

## Inputs
- `analysis.md`
- `cross_repo_analysis.md`
- `dependency_analysis.md`
- `gap_analysis.md`

## Execution Strategy
- Close all `P0` gaps first.
- Close `P1` gaps before declaring V0 “operational”.
- Defer `P2` gaps only if they are tracked and scheduled.

## Cross-Repo Work Plan

## Wave 0: Baseline Alignment (spawn + dotfiles)
### Objectives
- Remove immediate runtime drift before memory implementation.

### Tasks
- `spawn`:
  - keep generated artifacts current (`scripts/gen.sh`).
- `dotfiles`:
  - update `config/spawn/spawnd.toml` `source_command` to `python3 -m spawn.runtime.codex_event_source`.
  - resolve `spawn-api.service` socket dependency mismatch:
    - either add `spawn.socket`,
    - or remove `Wants/After=spawn.socket`.

### Exit criteria
- Services start cleanly with current code layout.
- No stale module paths in deploy config.

## Wave 1: Contract Authority Shift (spawn)
### Objectives
- Establish JSON Schema SSOT for persisted memory/event artifacts.

### Tasks
- add `src/spawn/ssot/schemas/` minimal pack:
  - `schema.index.json`
  - foundational schemas (event/evidence/reason/work/task/gate/promotion/run/state)
  - `memory.schema.json`
- version policy fields in all persisted envelopes:
  - `schema_name`
  - `schema_version`

### Exit criteria
- SSOT schemas locally resolve via `$ref`.
- Schema index is complete and machine-validated.

## Wave 2: Validation Substrate (spawn)
### Objectives
- Make schema validation mandatory at boundaries.

### Tasks
- implement:
  - `spawn/ssot/registry.py`
  - `spawn/ssot/validate.py`
- add CLI:
  - `spawnctl ssot list`
  - `spawnctl ssot validate-file <schema> <path>`
  - `spawnctl ssot validate-json <schema> --stdin`
- enforce validation at:
  - pre-dispatch,
  - worker-start,
  - post-result.

### Exit criteria
- Invalid payloads cannot dispatch.
- Invalid results cannot persist.
- Validation failures produce structured audit rows.

## Wave 3: Memory Store + Replay (spawn)
### Objectives
- Deliver durable memory SSOT and deterministic rebuild.

### Tasks
- add `memory.events.jsonl` append-only store.
- implement cursor model `(path, inode, offset, last_event_id)`.
- implement extractor v0 (rule-based) + gate policy v0.
- implement replay outputs:
  - `memory.accepted.json`
  - `memory.proposals.json`
  - `memory.prompt.txt` (derived).

### Exit criteria
- Replay from SSOT reproduces snapshots deterministically.
- Idempotency avoids duplicate memories across retries/reruns.

## Wave 4: Operator Loop (spawn)
### Objectives
- Complete review-driven memory lifecycle.

### Tasks
- implement CLI:
  - `spawnctl memory list`
  - `spawnctl memory proposals`
  - `spawnctl memory accept <proposal_id>`
  - `spawnctl memory reject <proposal_id>`
  - `spawnctl memory deprecate <memory_id>`
  - `spawnctl memory render`
  - `spawnctl memory rebuild`

### Exit criteria
- Full operator review and rebuild loop works without UI.

## Wave 5: CI + Governance (spawn + fabric-docs)
### Objectives
- Block drift and make spec-first enforcement automatic.

### Tasks
- add `spawn` CI workflow:
  - `scripts/check_gen.sh`
  - SSOT schema validation
  - contract/replay tests
- update `fabric-docs` stale watcher references affecting current ownership model.

### Exit criteria
- PRs fail on contract/schema drift.
- Standards docs match active architecture (`spawn`/`mesh` naming and boundaries).

## Dependency-Ordered Sequence
1. Wave 0 (runtime alignment)
2. Wave 1 (schema authority)
3. Wave 2 (validator + boundary enforcement)
4. Wave 3 (memory persistence/replay)
5. Wave 4 (operator commands)
6. Wave 5 (CI/governance hardening)

## Success Criteria (V0 Complete)
- P0 gaps closed (`G1-G4`).
- P1 gaps closed (`G5-G8`).
- Memory state is reconstructible from SSOT only.
- Cross-repo runtime wiring is consistent with current `spawn` implementation.
