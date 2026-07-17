# Terra-Cortex reliability alerts and dashboard

Prometheus evaluates Terra-Cortex reliability rules every 15 seconds. Grafana
automatically provisions the `Terra-Cortex Reliability` dashboard with the
stable UID `terra-cortex-reliability`.

## Alert policy

| Alert | Severity | Condition | Initial operator action |
| --- | --- | --- | --- |
| `TerraCortexTargetDown` | critical | Cortex scrape target down for 2 minutes | Check container status, restart history, and Kafka reachability. |
| `TerraCortexRuntimeNotReady` | critical | `terra_cortex_ready == 0` for 1 minute | Identify the down component and inspect the preceding task failure. |
| `TerraCortexCriticalTaskFailure` | critical | Critical task failure increased within 5 minutes | Confirm processing quiesced and the replica restarted with an uncommitted offset. |
| `TerraCortexRestartLoop` | critical | At least 3 observed process changes in 15 minutes | Stop the loop if necessary; check permanent configuration and broker failures. |
| `TerraCortexKafkaTransactionFailures` | warning | At least 3 failures in 5 minutes, sustained for 1 minute | Check broker health, fencing, timeouts, and retry growth. |
| `TerraCortexDeadLetteredEvents` | warning | Any DLT increase in 15 minutes | Inspect the DLT through an authorized operational workflow. |
| `TerraCortexEventIdConflicts` | warning | Any ID conflict increase in 15 minutes | Find the upstream producer violating stable event identity. |
| `TerraCortexReliabilityMetricsMissing` | warning | Target up but readiness metric absent for 5 minutes | Check metric contract/version mismatch. |
| `TerraCortexDedupeRestoreSlow` | warning | Latest restore over 60 seconds for 5 minutes | Check marker volume, retention, broker throughput, and segment cleanup. |

Alert annotations contain operational summaries only. They do not include event
IDs, payloads, fingerprints, broker addresses, or exception messages.

## Dashboard

The reliability dashboard shows:

- scrape health, readiness, fatal state, firing alerts, and process changes;
- consumer, producer, consumer task, restore, marker follower, and sweep state;
- processed, duplicate, DLT, and conflict rates;
- Kafka transaction failures, retries, and critical task failures;
- active dedupe markers, restore records scanned, and restore duration.

Both Grafana dashboards are file-provisioned from
`infra/grafana/dashboards`. UI edits are disabled so repository state remains the
source of truth. The Compose profile enables SQLite write-ahead logging and a
container restart policy so a transient first-start migration lock is retried.
SQLite remains appropriate only for this single-instance development profile;
production Grafana should use an external MySQL or PostgreSQL database.

## Validation

Prometheus configuration and alert expressions are checked with `promtool` in
CI. Rule unit tests cover target loss, readiness loss, task failure, restart
loop, transaction failures, DLT, identity conflict, missing metrics, and slow
restore. Docker E2E also verifies that Prometheus loads all rules and scrapes a
ready Cortex metric, and that Grafana serves the provisioned dashboard by UID.

```bash
docker run --rm --entrypoint /bin/promtool \
  -v "$PWD/infra/prometheus:/etc/prometheus:ro" \
  -w /etc/prometheus/tests \
  prom/prometheus:v2.48.0 \
  test rules terra-cortex-alerts.test.yml
```

## Notification routing and limits

This repository defines rule evaluation, severity, and runbook actions. It does
not embed Slack, email, PagerDuty, or other Alertmanager receivers because those
destinations and credentials are deployment-specific. Production must connect
Prometheus to an externally configured Alertmanager.

Restart-loop detection depends on observing the process-start metric at the
15-second scrape interval. Multiple restarts entirely between scrapes can be
missed, so container/orchestrator restart counts and logs remain complementary
signals. Thresholds are safe defaults and should be tuned from production
baseline data rather than silently changed in the dashboard.
