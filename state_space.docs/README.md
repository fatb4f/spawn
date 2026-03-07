# State Space Docs Consolidation

## Purpose

This directory is a research packet for `../state_space`.

It is not the authority. The authority remains the formal spec, schema artifacts, and proposal register under `../state_space`.

## Document Review

### Highest-signal

- `output_4.md`
  - Core model split: `source_space`, `transform_space`, `state_space`, `transition_space`
  - Best foundation for schema work
- `output_5.md`
  - Correct policy split: daemon shapes the world, policy decides admission, executor only runs admitted plans
  - Best foundation for gate contracts
- `output_3.md`
  - Correct OTel placement: transport and event boundary, not cache or business-state engine
- `output_2.md`
  - Strong snapshot/cache guidance: DTOs, cursors, consistency bounds, hot-cache rules

### Supporting

- `output_6.md`
  - Good later-stage governance/compliance projection via OSCAL
  - Not phase-1 runtime authority
- `output_7.md`
  - Useful runtime guardrail/control catalog
  - Better treated as a later execution-hardening profile

### Lower-signal for current scope

- `output_1.md`
  - Tooling comparison is directionally correct
  - It does not materially advance `state_space` contract design

## Normalized Architecture

1. Collect immutable source observations.
2. Apply named, versioned transforms.
3. Admit a bounded `state_space` projection.
4. Derive dependency graph and relevant neighborhood.
5. Build a compact policy input.
6. Evaluate admission policy.
7. Enforce only admitted transitions.
8. Project to governance/compliance formats if needed.

## Keep / Prune

### Keep now

- Source/transform/state/admission split
- Snapshot consistency metadata
- OTel logs as structured state-fact transport
- Small hot-path policy input

### Defer

- OSCAL adapter work
- Advanced runtime guardrails beyond baseline service hardening
- DSPy/tooling taxonomy

## Immediate Contract Candidates

These are the highest-signal artifacts to define next:

1. `observed.source.record`
2. `transform.spec`
3. `snapshot.meta`
4. `state_space_snapshot`
5. `live_state_event`
6. `policy.input`
7. `policy.decision`
8. `dependency.graph`
9. `runtime.guardrail.profile`
10. `oscal.adapter.view`

`runtime.guardrail.profile` and `oscal.adapter.view` are phase-2 candidates. The others are phase-1/phase-1.5 candidates.

## Recommended Execution Order

1. Define `observed.source.record`
2. Define `transform.spec`
3. Define `live_state_event`
4. Define `policy.input`
5. Define `policy.decision`
6. Refine `dependency.graph`
7. Add `userland.spec`
8. Add `runtime.guardrail.profile`
9. Add `oscal.adapter.view`

## Companion Artifacts

- `review.normalized.json`
- `high_signal_candidates.json`
- `high_signal_candidates.md`
