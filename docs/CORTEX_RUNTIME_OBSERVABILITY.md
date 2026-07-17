# Terra-Cortex runtime health and metrics

Terra-Cortex exposes separate process-liveness and work-readiness probes. This
prevents an HTTP-responsive replica from being treated as healthy after its
Kafka consumer or a dedupe maintenance task has terminated.

## Health endpoints

| Endpoint | Success | Contract |
| --- | --- | --- |
| `GET /health` | `200` | Backward-compatible legacy status; it is not a readiness gate. |
| `GET /health/live` | `200` | The FastAPI process can serve requests. No dependency checks. |
| `GET /health/ready` | `200` or `503` | All required Kafka and dedupe runtime components are up. |

Readiness requires all of the following:

- Kafka input consumer and transactional producer are started;
- the Kafka consumer task is still running;
- the read-committed dedupe marker restore completed;
- the marker follower task is still running;
- the in-memory expiry sweep task is still running.

An unready response contains only stable reason codes and component states. It
does not expose sensor payloads, fingerprints, event IDs, broker addresses, or
exception messages. Current reason codes are:

- `KAFKA_CONSUMER_NOT_READY`
- `KAFKA_PRODUCER_NOT_READY`
- `KAFKA_CONSUMER_TASK_STOPPED`
- `DEDUPE_RESTORE_INCOMPLETE`
- `DEDUPE_MARKER_FOLLOWER_STOPPED`
- `DEDUPE_EXPIRY_SWEEP_STOPPED`

The Cortex Docker image and CI/E2E service wait use `/health/ready`. A dead
background task therefore removes the replica from service and eventually makes
the container unhealthy. Liveness remains independent so an orchestrator can
distinguish a dead process from a live process that must not receive work.

## Prometheus endpoint

`GET /metrics` exposes process-local counters and current gauges. The existing
Prometheus configuration scrapes this endpoint every 15 seconds.

Core counters:

- `terra_cortex_events_processed_total`
- `terra_cortex_event_retries_total`
- `terra_cortex_events_dead_lettered_total`
- `terra_cortex_kafka_transaction_failures_total`
- `terra_cortex_duplicates_suppressed_total`
- `terra_cortex_event_id_conflicts_total`
- `terra_cortex_legacy_event_ids_generated_total`
- `terra_cortex_dedupe_expired_markers_total`

Core gauges:

- `terra_cortex_ready`
- `terra_cortex_kafka_consumer_up`
- `terra_cortex_kafka_producer_up`
- `terra_cortex_kafka_consumer_task_up`
- `terra_cortex_dedupe_restore_up`
- `terra_cortex_dedupe_marker_follower_up`
- `terra_cortex_dedupe_expiry_sweep_up`
- `terra_cortex_dedupe_active_markers`
- `terra_cortex_dedupe_restore_duration_seconds`
- `terra_cortex_dedupe_restore_records_scanned`

Counters reset when a Cortex process restarts; Prometheus `rate()`/`increase()`
handles counter resets. Gauges and readiness are replica-local. In a multi-replica
deployment, alert by instance first and aggregate event counters only when each
replica has a distinct Prometheus target label.

## Operational limits

The probes establish runtime task liveness, not end-to-end broker correctness.
A running client can still become temporarily unable to reach Kafka between
scrapes. Transaction failures and retry counters provide the complementary
signal. Readiness turns false when a task terminates; transient transaction
errors remain handled by the existing retry and DLT policy.
