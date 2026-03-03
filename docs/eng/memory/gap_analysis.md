# Gap Analysis (Memory V0)

## Rating Scale
- `P0`: blocks memory-first delivery
- `P1`: high-risk drift or reliability issue
- `P2`: quality/maintainability improvement

## Findings

| ID | Priority | Gap | Evidence | Impact | Required Fix | Status |
|---|---|---|---|---|---|---|
| G1 | P0 | No SSOT schema pack in `spawn` | Resolved via `src/spawn/ssot/schemas/*` + `schema.index.json` | Cannot enforce memory/event persistence contracts | Add migrated minimal schema set + `schema.index.json` | done |
| G2 | P0 | No schema registry/validator CLI | Resolved via `spawnctl ssot list|validate-*` | No boundary validation guardrails | Implement registry + `spawnctl ssot validate-*` | done |
| G3 | P0 | No memory contracts | Resolved via `memory.schema.json` + enforced event/task schemas | Cannot persist/operate memory store deterministically | Add `memory_item/proposal/patch/event` contracts | done |
| G4 | P0 | No memory persistence/rebuild pipeline | Resolved via `memory.events.jsonl` + rebuild commands | No durable memory SSOT | Implement append-only store + replay snapshots | done |
| G5 | P1 | Dotfiles config uses old module path | `dotfiles/config/spawn/spawnd.toml` had `python3 -m spawn.codex_event_source` | Runtime failure risk after refactor | Update to `python3 -m spawn.runtime.codex_event_source` | done |
| G6 | P1 | Unit references missing socket unit | `dotfiles/units/user/spawn-api.service` wanted `spawn.socket` without unit file | Service dependency ambiguity and startup ordering risk | Ship `spawn.socket` or remove dependency | done |
| G7 | P1 | No CI enforcement for generation/schema gates | no `.github/workflows` in `spawn` | Drift reaches main branch undetected | Add CI for `scripts/check_gen.sh` + schema validation | todo |
| G8 | P1 | Contract authority mismatch vs memory plan | current canonical = `contracts/models.py`; target = JSON Schema SSOT | Potential dual-authority drift | Partition authority: persisted contracts from `src/spawn/ssot/schemas`; transport from proto | in_progress |
| G9 | P2 | No integration tests for CLI/daemon contracts | no `tests/` in `spawn` | regression risk for RPC and schema behavior | Add baseline integration + replay tests | todo |
| G10 | P2 | Cross-repo docs still watcher-centric in places | `fabric-docs/docs/COMPONENTS.md` references watcher paths | Confusing ownership and migration status | Update docs to current spawn/mesh naming and artifacts | todo |

## Aggregate Status
- P0 gaps: 0 open
- P1 gaps: 2 open
- P2 gaps: 2 open

## Readiness Conclusion
- `spawn` now has a working memory-first baseline (contracts + ingestion + replay + operator CLI).
- Remaining work is reliability hardening (CI gates + tests) and cross-repo docs cleanup.
