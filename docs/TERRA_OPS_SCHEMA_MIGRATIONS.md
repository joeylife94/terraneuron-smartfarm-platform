# Terra-Ops schema migrations

Terra-Ops uses Flyway as the only schema-change mechanism. Hibernate runs with
`ddl-auto=validate`: it verifies the migrated schema at startup but never creates,
alters, or drops database objects.

## Migration layout

| Location | Scope | Contents |
|---|---|---|
| `db/migration` | Every environment | Versioned production schema and additive upgrades |
| `db/local` | `compose` profile only | Idempotent demo farms, sensors, crops, and BCrypt users |

`V1__create_terra_ops_schema.sql` is the canonical schema. It uses
`CREATE TABLE IF NOT EXISTS` so it can create a fresh database and adopt the tables
already present in a legacy volume. `V2__Reconcile_legacy_terra_ops_schema` adds the
command-correlation columns and indexes that the historical `init.sql` lacked.
`V3__Normalize_legacy_lifecycle_columns` converts lifecycle columns that Hibernate 6
may previously have created as native MySQL `ENUM` to the canonical `VARCHAR`
definitions while preserving their stored string values.

Lifecycle enums are persisted as `VARCHAR`, not MySQL native `ENUM`, so adding an
application state remains an explicit forward-compatible code/migration decision.
New production changes must be appended as `V4`, `V5`, and so on; an applied
migration must never be edited.

## Startup behavior

| Database state | Result |
|---|---|
| Empty | Flyway applies V1 through V3. The default profile creates no users or demo data. |
| Existing, no Flyway history | Flyway records baseline version 0, then applies V1 through V3 without dropping application tables or rows. |
| Already versioned | Flyway validates applied checksums and applies only pending migrations. |
| Docker Compose | The production path runs first, then the `compose` profile applies the local repeatable seed. |

Flyway coordinates concurrent startup through its schema-history lock, so multiple
Terra-Ops replicas do not independently apply the same migration. The application
becomes ready only after migrations and Hibernate validation succeed.

## Existing-volume rollout

1. Back up the MySQL database before the first deployment.
2. For a large `action_plans`, `audit_logs`, or `command_outbox` table, estimate
   the V3 `ALTER TABLE` duration and schedule a maintenance window.
3. Deploy Terra-Ops with the same database credentials and schema name.
4. Confirm V0, V1, V2, and V3 in `flyway_schema_history` and check the Terra-Ops startup log.
5. Verify that legacy application rows remain present, lifecycle columns report
   `DATA_TYPE = 'varchar'`, and the action-plan correlation schema exists.

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
  );
```

Do not delete or manually rewrite `flyway_schema_history`. Flyway `repair` is an
operator recovery action, not an automatic deployment step, and should be used only
after the database state and migration checksum have been reconciled deliberately.

## Guarantees and limits

- Adoption migrations do not drop tables, columns, or application rows.
- V3 only alters a targeted lifecycle column when its actual MySQL `DATA_TYPE` is
  `enum`; an already canonical `VARCHAR` column is left unchanged.
- Native ENUM values are converted to the same string value in `VARCHAR`, including
  existing action-plan, audit, and outbox rows.
- Production migrations never provision the repository's demo credentials.
- The Compose seed does not overwrite existing accounts and avoids duplicate demo
  records when its repeatable migration runs again.
- MySQL DDL auto-commits. A failed multi-statement migration cannot be rolled back as
  one transaction; restore from backup or complete a reviewed repair before retrying.
- Converting a populated native ENUM column can rebuild or lock its table depending on
  the MySQL version and storage conditions. Flyway serializes replicas, but it does not
  remove that database-level operational cost.
- Baseline version 0 means “compatible pre-Flyway Terra-Ops schema,” not arbitrary
  schema drift. Unknown manual changes can still fail Flyway or Hibernate validation
  and require a new explicit migration.
- Flyway provides forward migrations only. Database downgrade/rollback requires a
  separately reviewed migration or backup restoration.

## Verification

`TerraOpsSchemaMigrationTest` uses MySQL 8 through Testcontainers to cover both a
fresh database and a populated legacy database with Hibernate-style native ENUM
columns. It verifies baseline adoption, data/value preservation, V2 columns/indexes,
V3 type normalization, outbox creation, idempotent reruns, production seed isolation,
and the Compose seed. The repository E2E then boots the full Compose stack with
Hibernate validation enabled.
