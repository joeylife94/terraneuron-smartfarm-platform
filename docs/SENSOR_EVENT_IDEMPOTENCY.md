# Sensor Event Identity and Deduplication

## Contract

Every record on `raw-sensor-data` must carry an `eventId`, and the Kafka record key must be the same value.

An upstream provider may supply its own stable opaque ID. When no ID is supplied, Terra-Sense and Terra Data Collector derive one as:

```text
evt-<sha256(canonical measurement)>
```

The v1 canonical measurement is newline-separated:

```text
v1
farmId
sensorId
sensorType
timestamp as UTC epoch milliseconds
normalized numeric value
unit
```

The same physical measurement therefore produces the same ID across Java and Python. Changing any identity field produces a different ID.

## Cortex ledger

Terra-Cortex stores `eventId -> payload fingerprint` markers in the compacted Kafka topic `cortex-processed-event-ids`.

For a new event, Cortex commits these operations in one Kafka transaction:

1. Insight output
2. Optional Action Plan output
3. Event dedupe marker
4. Input consumer offset

For an already processed ID with the same fingerprint, Cortex skips AI analysis and commits only the duplicate input offset. A reused ID with a different fingerprint is sent to DLT as an identity conflict.

At startup Cortex replays the read-committed marker topic before starting the raw sensor consumer. A dedicated changelog follower then keeps every replica's local index current. Before a raw Kafka partition is assigned after a rebalance, that replica drains committed markers to the assignment-time end offsets. Because the marker and raw input offset are committed in the same Kafka transaction, a committed input cannot be handed to a new owner without its committed marker being visible to that owner.

## Retention window

`KAFKA_EVENT_DEDUPE_RETENTION_DAYS` configures a 30-day window by default. The window starts at Cortex `processed_at`, not at the sensor measurement timestamp. Processing time is intentional: delayed uploads and broker redelivery can contain an old sensor timestamp even though Cortex only just accepted the record.

Each marker contains:

```json
{
  "processed_at": "2026-07-17T00:00:00+00:00",
  "expires_at": "2026-08-16T00:00:00+00:00",
  "status": "PROCESSED"
}
```

`DEAD_LETTERED` markers use the same retention window. Therefore an identical poison record is suppressed during the window and may be attempted and dead-lettered again after expiry.

Within the window, the same `eventId` and fingerprint is suppressed and a different fingerprint is sent to DLT as `EVENT_ID_CONFLICT`. Once the marker expires, either payload is treated as new input and can produce a new Insight and Action Plan.

The in-memory index stores only active markers. It uses an expiry heap and a periodic sweep (`KAFKA_EVENT_DEDUPE_SWEEP_INTERVAL_SECONDS`, default 300 seconds), rather than scanning every ID for every event. Classification also checks the one requested ID, so an expired event is immediately treated as new even between sweeps.

## Kafka topic policy

The Cortex startup path creates or updates the marker topic with:

```text
cleanup.policy=compact,delete
retention.ms=<dedupe window>
delete.retention.ms=86400000
segment.ms=3600000
min.cleanable.dirty.ratio=0.1
```

Compaction keeps the latest value per `eventId`; deletion bounds even the latest value by segment age. Kafka retention is not an exact expiry clock: it deletes whole closed segments asynchronously, so records can remain on disk beyond `retention.ms` by approximately `segment.ms` plus the broker log-cleaner interval. Cortex correctness does not wait for physical deletion: startup skips expired values and the runtime index expires them at `expires_at`.

## Scaling requirement

All producers must use `eventId` as the raw Kafka key. This preserves per-ID order in the raw topic. The read-committed marker follower and rebalance catch-up close the replica hand-off gap; all replicas must use the same marker topic, retention settings, and Kafka cluster.

The guarantee is bounded duplicate suppression for committed Cortex processing inside one Kafka cluster and dedupe window. It does not cover producers that violate the key contract, events replayed after expiry, marker-topic data loss, cross-cluster active/active processing, external side effects outside the Kafka transaction, or pathological in-flight processing during repeated rebalances. Strict distributed exactly-once beyond those boundaries requires an authoritative partition-local state store such as Kafka Streams, or another shared conditional-write store.

## Compatibility

Historical records without `eventId` are assigned the same deterministic v1 ID by Cortex. The compatibility path is observable through `legacy_event_ids_generated` and should trend to zero after all producers are upgraded.

## Operations

```text
GET /api/kafka/deduplication
```

The endpoint reports:

- configured processing-time retention
- active and observed-expired marker counts
- startup records scanned, expired records skipped, active IDs loaded, and restore duration
- last and next sweep time
- compact/delete topic configuration
- duplicate, conflict, and legacy-ID counters

It never returns sensor payloads, fingerprints, event IDs, or secrets.
