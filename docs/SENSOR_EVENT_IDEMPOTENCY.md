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

At startup Cortex replays the read-committed compacted marker topic before starting the raw sensor consumer. This preserves semantic deduplication across process and container restarts.

## Scaling requirement

All producers must use `eventId` as the raw Kafka key. This guarantees duplicate records are assigned to the same partition and therefore the same active Cortex consumer in a consumer group.

## Compatibility

Historical records without `eventId` are assigned the same deterministic v1 ID by Cortex. The compatibility path is observable through `legacy_event_ids_generated` and should trend to zero after all producers are upgraded.

## Operations

```text
GET /api/kafka/deduplication
```

The endpoint reports ledger topic, restored marker count, loaded unique events, suppressed duplicates, identity conflicts, and legacy ID generation. It never returns sensor payloads or secrets.
