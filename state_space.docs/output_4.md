## Recommendation

Treat `state_space` as a **versioned, admissible domain projection**, not as a direct mirror of the runtime.

That gives you:

* **first-class sources**
* **explicit transforms**
* **derived state**
* **known-good transitions on the derived state**

Pydantic is a good fit for the contract layer because its models are explicit schemas, can generate JSON Schema, and can serialize to Python/JSON forms for storage or transport. ([Pydantic][1])

## The modeling split

You have four different things. Keep them separate.

### 1. `source_space`

These are the only first-class observations:

* dotfiles
* resolved config fragments
* `systemctl show` / unit property snapshots
* journal entries or journal slices
* listener-emitted events
* collector ingress envelopes

For journald, treat the cursor as **opaque provenance**, not domain meaning; the journal docs describe `__CURSOR` as an opaque position token. ([man7.org][2])

### 2. `transform_space`

This is the part you still need to shape.

A transform should be a **named, versioned contract**:

```text
Transform:
  input_schema
  output_schema
  preconditions
  invariants_preserved
  determinism_level
  provenance_rules
  version
```

This is the missing middle between inputs and outputs.

### 3. `state_space`

This is not raw runtime. It is the **typed result of applying transforms to sources**.

Think of it as:

```text
state_space = reduce(transforms(source_space))
```

The cache is just the current materialized instance of that reduction.

### 4. `transition_space`

A transition is valid only if it moves one admissible state to another admissible state.

So the real contract is not just:

```text
input -> output
```

It is:

```text
(source facts, previous state) -> transform -> candidate state -> invariant check -> admitted state
```

---

## The key design choice

You asked whether to:

* shape the transforms, or
* find an acceptable representation with first-class only data-sources

The clean answer is:

## Do both, but privilege sources over state

Use **first-class source records** as the durable truth, and make **transforms first-class and versioned** so `state_space` can always be rebuilt.

That gives you:

* replay
* cache rebuild
* schema evolution
* deterministic testing
* provenance
* safer migration when contracts change

If you instead make `state_space` the only primary artifact, you lose too much information about how it was derived.

---

## A good draft shape

### Layer A — Observations

Immutable, append-only, source-specific.

Examples:

* `DotfileObserved`
* `SystemdUnitObserved`
* `JournalEntryObserved`
* `ListenerEventObserved`

### Layer B — Normalized facts

Still source-grounded, but contract-clean.

Examples:

* `UnitRuntimeFact`
* `ConfigFact`
* `ServiceHealthFact`
* `JournalFact`

### Layer C — Derived state

The thing you actually reason over.

Examples:

* `ServiceState`
* `DependencyState`
* `SnapshotState`
* `ConvergenceState`

### Layer D — Transition judgments

State machine rules.

Examples:

* `Unknown -> Observed`
* `Observed -> Reconciling`
* `Reconciling -> KnownGood`
* `KnownGood -> Drifted`
* `Drifted -> Recovering`

---

## What “known-good” should mean

Do not define `known_good_state` as “all expected fields are present.”

Define it by **invariants**.

Examples:

* required sources present
* all transforms completed successfully
* source timestamps are within freshness bounds
* all referenced units belong to the same boot/session scope
* no unresolved contradiction between config facts and runtime facts
* journal coverage is continuous up to the admitted cursor
* dependency closure is satisfied

That way, `known_good_state` is a **judged state**, not merely a populated document.

---

## The transform taxonomy

This usually helps:

### 1. Parse transforms

Raw source → typed source model

Example:

* dotfile text → `DotfileObserved`

### 2. Normalize transforms

Source model → canonical fact

Example:

* different unit/property shapes → `UnitRuntimeFact`

### 3. Correlation transforms

Join facts across sources

Example:

* systemd unit + journal slice + config override → `ServiceHealthFact`

### 4. Reduction transforms

Facts + previous state → next state

Example:

* incoming delta + current cache → `SnapshotState`

### 5. Admission transforms

Candidate state → accepted/rejected state

Example:

* `CandidateSnapshotState` → `KnownGoodSnapshotState`

This is the part that should be explicit and versioned.

---

## What the hot cache should be

Use the hot cache as a **materialized projection** only.

It should contain:

* current admitted state
* provenance to the source facts used
* transform version set
* last applied journal cursor
* snapshot/version metadata

It should **not** be the only truth.

That is especially important because the Collector is designed to receive, process, and export telemetry through pipelines of receivers, processors, exporters, and connectors; it is a transport/processing layer, not your domain state engine. ([OpenTelemetry][3])

---

## Where OTel fits in this draft

Use OTel to carry:

* source observations
* transform execution spans
* state-delta events
* cache admission decisions

OpenTelemetry has separate signals for traces, metrics, and logs, and logs are explicitly modeled as structured records that can represent machine-generated events and system logs. Span events are point-in-time happenings inside a span, while traces/spans represent operations. ([OpenTelemetry][4])

For your model:

* **logs**: source observations and state deltas
* **spans**: transform execution / snapshot refresh workflows
* **metrics**: lag, freshness, admission failures, drift counts

That keeps the domain contract clean.

---

## The simplest viable representation

If you want a strong draft quickly, define only these first-class contracts:

```text
ObservedSourceRecord
NormalizedFact
CandidateState
AdmittedState
StateDelta
TransitionRule
AdmissionResult
```

And require that every `AdmittedState` has:

```text
state_id
schema_version
transform_set_version
source_refs[]
admitted_at
admission_result
known_good: bool
```

That is enough to let you:

* replay from sources
* materialize cache
* inspect provenance
* test transitions
* evolve schemas

---

## The decision rule

If a field cannot be traced back to a first-class source or a named transform, it does not belong in `state_space`.

That one rule prevents most schema drift.

---

## My recommendation for the draft

Define `state_space` as:

> the smallest versioned, admissible representation of system condition that can be deterministically re-derived from first-class source records and versioned transforms

Then make the cache:

> the latest admitted materialization of that representation

That gives you a clean path to:

* Pydantic contracts for every layer
* OTel transport for observations/deltas
* replay from source records
* known-good transitions as admission rules

## Practical next step

Draft these three models first:

1. `ObservedSourceRecord`
2. `StateDelta`
3. `AdmittedState`

Once those are stable, the transform layer becomes much easier to specify.

[1]: https://docs.pydantic.dev/latest/concepts/json_schema/?utm_source=chatgpt.com "JSON Schema - Pydantic Validation"
[2]: https://man7.org/linux/man-pages/man1/journalctl.1.html?utm_source=chatgpt.com "journalctl(1) - Linux manual page"
[3]: https://opentelemetry.io/docs/collector/architecture/?utm_source=chatgpt.com "Architecture"
[4]: https://opentelemetry.io/docs/concepts/signals/?utm_source=chatgpt.com "Signals"

