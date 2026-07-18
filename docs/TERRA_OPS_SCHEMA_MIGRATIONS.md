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
Lifecycle enums are persisted as `VARCHAR`, not MySQL native `ENUM`, so adding an
application state remains an explicit forward-compatible code/migration decision.
New production changes must be appended as `V3`, `V4`, and so on; an applied
migration must never be edited.

## Startup behavior

| Database state | Result |
|---|---|
| Empty | Flyway applies V1 and V2. The default profile creates no users or demo data. |
| Existing, no Flyway history | Flyway records baseline version 0, then applies V1 and V2 without dropping application tables or rows. |
| Already versioned | Flyway validates applied checksums and applies only pending migrations. |
| Docker Compose | The production path runs first, then the `compose` profile applies the local repeatable seed. |

Flyway coordinates concurrent startup through its schema-history lock, so multiple
Terra-Ops replicas do not independently apply the same migration. The application
becomes ready only after migrations and Hibernate validation succeed.

## Existing-volume rollout

1. Back up the MySQL database before the first deployment.
2. Deploy Terra-Ops with the same database credentials and schema name.
3. Confirm V0, V1, and V2 in `flyway_schema_history` and check the Terra-Ops startup log.
4. Verify that `legacy` application rows remain present and that
   `command_outbox` plus the action-plan correlation columns exist.

Useful read-only check:

```sql
SELECT installed_rank, version, description, type, success, installed_on
FROM flyway_schema_history
ORDER BY installed_rank;
```

Do not delete or manually rewrite `flyway_schema_history`. Flyway `repair` is an
operator recovery action, not an automatic deployment step, and should be used only
after the database state and migration checksum have been reconciled deliberately.

## Guarantees and limits

- Adoption migrations are additive: they do not drop tables, columns, or rows.
- Production migrations never provision the repository's demo credentials.
- The Compose seed does not overwrite existing accounts and avoids duplicate demo
  records when its repeatable migration runs again.
- MySQL DDL auto-commits. A failed multi-statement migration cannot be rolled back as
  one transaction; restore from backup or complete a reviewed repair before retrying.
- Baseline version 0 means “compatible pre-Flyway Terra-Ops schema,” not arbitrary
  schema drift. Unknown manual changes can still fail Flyway or Hibernate validation
  and require a new explicit migration.
- Flyway provides forward migrations only. Database downgrade/rollback requires a
  separately reviewed migration or backup restoration.

## Verification

`TerraOpsSchemaMigrationTest` uses MySQL 8 through Testcontainers to cover both a
fresh database and a populated legacy database. It verifies baseline adoption, data
preservation, V2 columns/indexes, outbox creation, idempotent reruns, production seed
isolation, and the Compose seed. The repository E2E then boots the full Compose stack
with Hibernate validation enabled.
