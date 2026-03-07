## Yes — that rationale is solid

The clean interpretation is:

* the **daemon** is your **policy enforcement point**
* **OPA/Rego** is the **policy decision point**
* `state_space` is the **typed decision context**
* the agent loop only gets **promoted from plan → execute** if policy admits it

That aligns with OPA’s model of separating **decision-making** from **enforcement**, and with Rego’s design around querying **structured JSON-like documents**. ([Open Policy Agent][1])

## The strongest version of the design

Do **not** make the daemon “understand all of userspace” as one giant mutable object.

Make it own a **bounded world model**:

1. **Observed sources**

   * dotfiles
   * systemd/unit properties
   * journal slices
   * listener-emitted events

2. **Derived facts**

   * dependency edges
   * readiness / drift / freshness
   * capability / risk / provenance flags

3. **Plan proposal**

   * what the agent wants to do
   * required preconditions
   * expected writes / side effects
   * rollback or compensation info

4. **Policy input**

   * `input = { plan, actor, current_state, facts, graph, constraints }`

That fits Rego well because Rego is meant to make decisions over **hierarchical structured data**, especially JSON-shaped documents. ([Open Policy Agent][2])

---

## What `state_space` should be in this setup

For this use case, `state_space` should not be “the runtime.”

It should be:

> the minimum admissible representation of userspace needed to make safe promotion decisions

That means it should contain only data needed for policy:

* identity of entities
* dependency graph
* freshness/version markers
* state classifications
* risk flags
* unresolved conflicts
* provenance refs
* allowed transitions

Not raw handles, live streams, or opaque runtime objects.

---

## Better split: policy data vs policy input

OPA distinguishes between **data** and **input** in practice:

* **`data`**: relatively stable policy data and bundled facts
* **`input`**: per-decision request context

OPA bundles can package policies and hierarchical data documents together. ([Open Policy Agent][3])

For your design, that suggests:

### Put in `data`

* dependency graph templates
* stable capability maps
* policy configuration
* known service classes
* transition rules
* trust classifications

### Put in `input`

* current candidate plan
* current admitted `state_space`
* live freshness markers
* current graph deltas
* current actor/session
* current risk signals

This keeps policy evaluation small and predictable.

---

## The daemon’s job

The daemon should do three things only:

### 1. Build and maintain the admissible state model

This is your materialized `state_space`.

### 2. Convert a proposed plan into a policy request

This is the **promotion request**, not the execution itself.

### 3. Enforce the decision

Allow promotion, deny it, or require additional conditions.

That separation is important because OPA is strongest when asked a narrow question like:

* `allow?`
* `deny reasons?`
* `required approvals?`
* `missing preconditions?`

---

## The policy question should be framed as admission control

This is the right mental model:

```text
candidate_plan + current_state + dependency_graph + actor_context
    -> policy decision
    -> admitted | denied | deferred
```

That is much cleaner than trying to encode the whole agent loop in policy.

OPA is commonly used as a PDP in front of runtime actions, and OPA deployment guidance explicitly discusses PEP/PDP placement and the tradeoff between local low-latency decisions versus centralized decisions. ([Open Policy Agent][1])

---

## How to shape the transforms

You said:

* input is known
* output is known
* transforms need shape

For this architecture, transforms should be first-class and versioned.

A good transform contract is:

```text
TransformSpec:
  name
  version
  input_schema
  output_schema
  dependencies
  determinism
  freshness_requirements
  invariant_checks
```

Then `state_space` becomes:

```text
state_space = admitted(reduce(transform_specs, source_records))
```

That gives you a model where policy can ask:

* Was this state derived from the required sources?
* Are the sources fresh enough?
* Did all required transforms succeed?
* Are dependency invariants satisfied?
* Is the proposed next action valid from this current state?

---

## Recommended policy shape

The top-level Rego input document should be small and explicit:

```json
{
  "plan": {
    "id": "plan-123",
    "intent": "restart_unit",
    "target": "user.slice/foo.service",
    "requires": ["unit-visible", "journal-fresh", "deps-healthy"],
    "effects": ["service-interruption"]
  },
  "actor": {
    "agent_id": "agent-a",
    "role": "planner"
  },
  "state": {
    "version": "v3",
    "known_good": true,
    "freshness_ms": 420,
    "boot_id": "..."
  },
  "facts": {
    "target_active_state": "active",
    "journal_gap": false
  },
  "graph": {
    "blocked_by": ["db.service"],
    "dependents": ["ui.service"]
  }
}
```

Then policy answers things like:

* deny if `state.known_good` is false
* deny if freshness exceeds threshold
* deny if graph contains blocked dependencies
* deny if plan effects exceed actor role
* require manual approval for certain effects

That is exactly the kind of hierarchical input Rego is built for. ([Open Policy Agent][2])

---

## Where Pydantic fits

Pydantic should define the producer-side contracts:

* `ObservedSourceRecord`
* `DerivedFact`
* `DependencyGraph`
* `PlanProposal`
* `PolicyInput`
* `PolicyDecision`

Use it to ensure the daemon never hands malformed decision input to policy.

OPA’s tooling can validate references to `input` and `data` against JSON Schemas during evaluation with the `--schema` flag, which is useful for CI and test validation. ([Open Policy Agent][4])

A practical split is:

* **Pydantic** = schema ownership and serialization
* **OPA/Rego** = decision logic
* **daemon** = source collection, transform execution, enforcement

---

## Hot path vs cold path

For the promotion gate, you want a very small hot path.

### Hot path

* current admitted state
* relevant graph neighborhood
* candidate plan
* actor/session
* current freshness/risk flags
* local policy evaluation

### Cold path

* full journal replay
* deep recomputation
* graph rebuild
* historical analysis

This matters because OPA documents explicit performance considerations for very low-latency policy decisions, and also documents compiling policies to Wasm for embedded evaluation paths. Wasm support is strong, though some built-ins are not supported natively. ([Open Policy Agent][5])

So for your gate:

* local OPA or embedded policy evaluation is appropriate
* keep the input small
* avoid expensive policy-time joins over giant state blobs

---

## Best representation choice

Between your two options:

### Option A — shape transforms

**Yes.** This is necessary.

### Option B — first-class only data-sources

**Also yes, but only as source-of-truth.**

The best combined model is:

```text
first-class source records
    -> versioned transforms
    -> admitted state_space
    -> policy gate for plan promotion
```

That is the robust architecture.

If you skip first-class source records, you lose rebuildability.
If you skip explicit transforms, you lose auditability and change control.

---

## The most important boundary

Do not ask policy to infer the world.

Ask policy to adjudicate a **candidate action against an already-shaped world model**.

So:

* daemon shapes the world
* policy approves or rejects transitions
* executor performs only admitted plans

That keeps the policy surface narrow and testable.

---

## Recommended core contracts

These are the minimum first-class models I would stabilize first:

* `ObservedSourceRecord`
* `DerivedFact`
* `DependencyGraph`
* `AdmittedStateSpace`
* `PlanProposal`
* `PolicyInput`
* `PolicyDecision`

Everything else can iterate around those.

## Bottom line

Your rationale is coherent, and it points to a specific architecture:

* **daemon** as world-model builder + enforcement point
* **OPA/Rego** as admission controller for plan promotion
* **state_space** as a typed, admissible projection of userspace
* **dependency graph** as first-class policy data
* **hot cache** as the current admitted projection
* **agent loop** only executes after policy approval

The sharpest formulation is:

> policy does not decide what the world is; policy decides whether a proposed transition is allowed, given an admitted model of the world.

I can turn this into a concrete schema set next: `PlanProposal`, `AdmittedStateSpace`, and `PolicyInput`, with Rego rule layout around `allow`, `deny`, and `require_approval`.

[1]: https://openpolicyagent.org/docs/deploy/k8s "Deploying OPA on Kubernetes | Open Policy Agent"
[2]: https://openpolicyagent.org/docs/policy-language "Policy Language | Open Policy Agent"
[3]: https://openpolicyagent.org/docs/management-bundles "Bundles | Open Policy Agent"
[4]: https://openpolicyagent.org/docs/cli "CLI Reference | Open Policy Agent"
[5]: https://openpolicyagent.org/docs/policy-performance "Policy Performance | Open Policy Agent"

