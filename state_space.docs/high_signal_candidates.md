# High-Signal Candidates

## Phase 1

1. `observed.source.record`
   - Foundational source envelope for dotfiles, unit facts, journal slices, and listener events.
2. `transform.spec`
   - Missing middle layer between durable observations and admitted state.
3. `live_state_event`
   - Canonical direct/enrich event contract for reducer and hot-cache updates.
4. `policy.input`
   - Compact, deterministic admission request.
5. `policy.decision`
   - Gate result contract with reasons and evidence.
6. `dependency.graph`
   - Core relation model for impact and transition gating.

## Phase 1.5

7. `snapshot.meta`
   - Reusable capture, freshness, boot, and consistency semantics.
8. `state_space_snapshot`
   - Admitted projection contract once source, transform, and event shapes are stable.

## Phase 2

9. `runtime.guardrail.profile`
   - Declarative execution hardening profile for runtime surfaces.
10. `oscal.adapter.view`
   - Governance/compliance projection, not runtime authority.
