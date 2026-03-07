Yes. That is a sound pattern, with one adjustment:

## Use OTel as the transport and contract boundary, not as the cache itself

OpenTelemetry is built around three stable signals—**traces, metrics, and logs**—and the Collector is designed to **receive, process, and export** those signals through pipelines composed of receivers, processors, exporters, and connectors. ([OpenTelemetry][1])

For your case, the clean split is:

* **cache / `live_state`** = materialized state view
* **OTel** = normalized event transport with schema/version metadata
* **collector** = routing/processing/fan-out layer
* **state consumer** = deterministic cache updater

## Signal choice

Using **spans alone** as the mutation trigger is possible, but I would not make them the only source of truth.

OpenTelemetry defines a **span** as the record of an operation with a start and end, while a **span event** is a meaningful singular point during that span. A **log record** is the recording of an event. **Metrics** are pre-aggregated timeseries measurements rather than event envelopes. ([OpenTelemetry][2])

That maps well to your design:

* **Span**: `state_space.snapshot.refresh`
* **Span events**: `journal.slice.loaded`, `unit.changed`, `dotfile.reparsed`
* **Log records**: actual discrete state-change payloads from listeners, journald-derived events, contract-bound update facts
* **Metrics**: cache freshness, collector lag, snapshot duration, delta volume, staleness counts

## For non-native emitters

Your listener approach is correct:

1. observe source event
2. normalize to contract
3. emit as OTel
4. forward to collector
5. update cache from the normalized stream

I would usually encode a non-native state mutation as a **structured log record** or a **span event inside a span**, depending on whether you need an operation envelope. Logs are the better default for discrete event payloads; spans are better when the event belongs to a bounded workflow with causality and duration. ([OpenTelemetry][3])

## Contract binding

Yes, bind each emitted record to a contract.

OpenTelemetry supports **semantic conventions** for common naming, and its schema model uses **Schema URLs** so telemetry producers can evolve emitted schemas over time while identifying which schema version a record follows. ([OpenTelemetry][4])

For your payloads, carry at least:

* `schema_url` or equivalent schema/version field
* `snapshot_id`
* `boot_id`
* `host_id`
* `state_space.namespace`
* `event_type`
* `entity_key`
* `observed_at`
* `sequence` or cursor
* `idempotency_key`

## Hot-cache usage

Yes, a hot cache works well here, provided it is updated from **contracted, replayable events**, not raw runtime objects.

A good model is:

* periodic **full snapshot**
* continuous **delta stream**
* cache holds the latest materialized state
* replay can rebuild cache from snapshot + deltas

That works especially well when journal-like sources already give you ordered continuation points, and when each update record is idempotent.

## What to avoid

### 1) Do not use metrics as the authoritative state feed

Metrics are for measurements and aggregation. They are not the right primary carrier for precise mutation payloads. ([OpenTelemetry][5])

### 2) Do not let the collector become the business-state engine

The Collector is excellent at ingesting, processing, routing, and exporting telemetry, and connectors can bridge pipelines or even change signal types. But I would still keep cache mutation in a dedicated consumer that reads the normalized telemetry stream. ([OpenTelemetry][6])

### 3) Do not rely on raw span structure for full domain semantics

Put domain facts into explicit attributes/body fields under your contract, not only in span names.

## Stronger version of your design

### Recommended shape

* listener emits **structured log record** for each state mutation
* optional parent span wraps the refresh / collection operation
* collector routes logs/traces
* dedicated state reducer updates `live_state`
* derived metrics are computed from the event stream or by connector/processor

This also aligns with the metrics data model, which explicitly supports generating metrics from streams of spans or logs, and with Collector connectors, which can summarize, replicate, or route across pipelines. ([OpenTelemetry][7])

## Practical rule

If the thing answers:

* **“what operation is in progress?”** → span
* **“what exact state fact changed?”** → log record
* **“what happened at this instant inside an operation?”** → span event
* **“how much / how often / how long?”** → metric

## Bottom line

Your plan is feasible and structurally good.

The version I would endorse is:

* **contract-bound event emitter**
* **OTel logs for state facts**
* **spans for collection/update workflows**
* **metrics derived from those streams**
* **collector for transport/routing**
* **hot cache as a materialized projection**

That gives you typed contracts, replayability, schema evolution, and cleaner cache semantics than “update cache directly from spans.”

I can turn this into a concrete event model next: `StateDelta`, `SnapshotEnvelope`, and `CacheReducer` with Pydantic types.

[1]: https://opentelemetry.io/docs/?utm_source=chatgpt.com "Documentation"
[2]: https://opentelemetry.io/docs/concepts/signals/traces/?utm_source=chatgpt.com "Traces"
[3]: https://opentelemetry.io/docs/concepts/signals/logs/?utm_source=chatgpt.com "OpenTelemetry Logs"
[4]: https://opentelemetry.io/docs/concepts/semantic-conventions/?utm_source=chatgpt.com "Semantic Conventions"
[5]: https://opentelemetry.io/docs/specs/otel/overview/?utm_source=chatgpt.com "Overview"
[6]: https://opentelemetry.io/docs/collector/architecture/?utm_source=chatgpt.com "OpenTelemetry Collector - Architecture"
[7]: https://opentelemetry.io/docs/specs/otel/metrics/data-model/?utm_source=chatgpt.com "Metrics Data Model"

