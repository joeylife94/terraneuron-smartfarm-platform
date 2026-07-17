# Terra-Cortex runtime health and metrics

Terra-Cortex exposes separate process-liveness and work-readiness probes. This
prevents an HTTP-responsive replica from being treated as healthy after its
Kafka consumer or a dedupe maintenance task has terminated.

## Health endpoints

| Endpoint | Success | Contract |
| --- | --- | --- |
| `GET /health` | `200` | Backward-compatible legacy status; it is not a readiness gate. |
| `GET /health/live` | `200` or `503` | The process is alive and no critical background task has failed. |
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
background task therefore makes the replica unready immediately. Because Cortex
is primarily a Kafka worker rather than an HTTP request service, losing one of
the consumer, marker follower, or expiry sweep tasks is fatal: `/health/live`
returns `503`, and the runtime requests graceful process termination after
`CORTEX_FATAL_TASK_EXIT_DELAY_SECONDS` (default 5 seconds). Docker Compose uses
`restart: unless-stopped`, while production orchestrators should restart the
exited replica with backoff.

On the first fatal signal, the supervisor immediately cancels the other critical
tasks before waiting for the exit delay. This quiesces raw consumption and aborts
an in-flight Kafka transaction, preventing the replica from processing against a
stale dedupe view during the diagnostic grace period.

Normal SIGTERM shutdown sets the supervisor to stopping before cancelling tasks,
so expected cancellation does not increment failure counters or schedule another
termination. If a Kafka transaction was in flight when a task failed, the
existing transactional producer aborts it and the uncommitted input offset is
eligible for redelivery after restart.

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
- `terra_cortex_critical_task_failures_total`

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
- `terra_cortex_runtime_fatal`
- `terra_cortex_process_termination_scheduled`
- `terra_cortex_process_start_time_seconds`

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

The supervisor does not restart individual tasks in place. A whole-process
restart rebuilds the read-committed dedupe ledger and Kafka clients from a known
state, avoiding a partially recovered replica. A permanent configuration or
broker problem can therefore produce a restart loop; the deployment platform
must apply restart backoff and alert on repeated restarts.

Prometheus alert thresholds, the Grafana reliability dashboard, and notification
routing boundaries are documented in
[`CORTEX_RELIABILITY_ALERTS.md`](CORTEX_RELIABILITY_ALERTS.md).
