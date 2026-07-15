# Authoritative E2E Gate

The integration workflow proves the following path with a unique farm identifier for every run:

1. Authenticate against terra-ops and obtain a JWT.
2. Submit four validated sensor readings to terra-sense.
3. Confirm terra-sense publishes the readings to Kafka.
4. Confirm terra-cortex consumes and analyzes the readings.
5. Confirm processed insights are validated and persisted by terra-ops.
6. Query the run-scoped insights through the authenticated API.
7. Verify the dashboard summary is consistent with the persisted results.

The test exits with a non-zero status for authentication failures, rejected ingestion, missing or malformed acknowledgements, API errors, missing insights, and polling timeouts.

CI also validates Docker Compose configuration and requires terra-sense, terra-cortex, terra-ops, and terra-gateway health endpoints before sending data. Diagnostic logs are uploaded on every run.
