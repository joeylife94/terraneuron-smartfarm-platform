# Terra-Ops schema migrations

Terra-Ops uses Flyway as the only schema-change mechanism. Hibernate runs with
`ddl-auto=validate`: it verifies the migrated schema at startup but never creates,
alters, or drops database objects.

## Migration layout

| Location | Scope | Contents |
|---|---|---|
| `db/migration` | Every environment | Versioned production schema and additive upgrades |
| `db/local` | `compose` profile only | Idempotent demo farms, sensors, crops, and BCrypt users |

Production migrations currently include:

| Version | Purpose |
|---|---|
| V1 | Canonical Terra-Ops schema and non-destructive table adoption |
| V2 | Legacy action-plan command-correlation columns and indexes |
| V3 | Native MySQL lifecycle `ENUM` normalization to `VARCHAR` |
| V4 | `SAFETY_BLOCKED` metadata and lifecycle support |
| V5 | Action-plan, command and outbox reference reconciliation |
| V6 | Persisted refresh-token session, rotation-family and revocation schema |

`V1__create_terra_ops_schema.sql` uses `CREATE TABLE IF NOT EXISTS` so it can create a fresh database and preserve tables already present in a compatible legacy volume. Later migrations reconcile missing or historical structures explicitly.

Lifecycle enums are persisted as `VARCHAR`, not MySQL native `ENUM`, so adding an application state remains an explicit forward-compatible code/migration decision. New production changes must be appended as V7 and later; an applied migration must never be edited.

## Startup behavior

| Database state | Result |
|---|---|
| Empty | Flyway applies V1 through V6. The default profile creates no users or demo data. |
| Existing, no Flyway history | Flyway records baseline version 0, then applies V1 through V6 without dropping application tables or rows. |
| Already versioned | Flyway validates applied checksums and applies only pending migrations. |
| Docker Compose | The production path runs first, then the `compose` profile applies the local repeatable seed. |

Flyway coordinates concurrent startup through its schema-history lock, so multiple Terra-Ops replicas do not independently apply the same migration. The application becomes ready only after migrations and Hibernate validation succeed.

## Existing-volume rollout

1. Back up the MySQL database before the first deployment.
2. For a large `action_plans`, `audit_logs`, or `command_outbox` table, estimate the legacy reconciliation duration and schedule an appropriate maintenance window.
3. Deploy Terra-Ops with the same database credentials and schema name.
4. Confirm V0 through V6 in `flyway_schema_history` and check the Terra-Ops startup log.
5. Verify that legacy rows remain present, lifecycle columns report `DATA_TYPE = 'varchar'`, command references are consistent and `refresh_token_sessions` exists.

Useful read-only checks:

```sql
SELECT installed_rank, version, description, type, success, installed_on
FROM flyway_schema_history
ORDER BY installed_rank;

SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND (
    (TABLE_NAME = 'action_plans' AND COLUMN_NAME IN ('status', 'priority'))
    OR (TABLE_NAME = 'audit_logs' AND COLUMN_NAME = 'event_type')
    OR (TABLE_NAME = 'command_outbox' AND COLUMN_NAME = 'status')
    OR (TABLE_NAME = 'refresh_token_sessions' AND COLUMN_NAME IN
        ('token_id', 'token_hash', 'family_id', 'revoked_at'))
  );
```

Do not delete or manually rewrite `flyway_schema_history`. Flyway `repair` is an operator recovery action, not an automatic deployment step, and should be used only after the database state and migration checksum have been reconciled deliberately.

## V6 refresh-token storage

V6 creates `refresh_token_sessions` with unique token-ID and SHA-256 digest constraints, username/family/expiry indexes, rotation replacement correlation and revocation metadata.

The table does not contain a raw refresh JWT. Multiple login sessions use different family IDs. A successful refresh revokes one row and inserts its replacement transactionally; reuse handling can revoke all still-active rows in that family.

Expired and revoked rows are retained until a separately defined retention job removes them.

## Guarantees and limits

- Adoption migrations do not drop tables, columns, or application rows.
- V3 only alters a targeted lifecycle column when its actual MySQL `DATA_TYPE` is `enum`; an already canonical `VARCHAR` column is left unchanged.
- Native ENUM values are converted to the same string value in `VARCHAR`, including existing action-plan, audit and outbox rows.
- V4 through V6 are additive or reconciliation migrations and do not provision production credentials.
- Production migrations never provision the repository's demo credentials.
- The Compose seed does not overwrite existing accounts and avoids duplicate demo records when its repeatable migration runs again.
- MySQL DDL auto-commits. A failed multi-statement migration cannot be rolled back as one transaction; restore from backup or complete a reviewed repair before retrying.
- Converting a populated native ENUM column can rebuild or lock its table depending on the MySQL version and storage conditions. Flyway serializes replicas, but it does not remove that database-level operational cost.
- Baseline version 0 means “compatible pre-Flyway Terra-Ops schema,” not arbitrary schema drift. Unknown manual changes can still fail Flyway or Hibernate validation and require a new explicit migration.
- Flyway provides forward migrations only. Database downgrade/rollback requires a separately reviewed migration or backup restoration.

## Verification

`TerraOpsSchemaMigrationTest` uses MySQL 8 through Testcontainers to cover both a fresh database and a populated legacy database with Hibernate-style native ENUM columns. It verifies baseline adoption, data/value preservation, command/outbox reconciliation, safety metadata, V6 refresh-token table columns and indexes, idempotent reruns, production seed isolation and the Compose seed.

The repository E2E then boots the full Compose stack with Hibernate validation enabled.
