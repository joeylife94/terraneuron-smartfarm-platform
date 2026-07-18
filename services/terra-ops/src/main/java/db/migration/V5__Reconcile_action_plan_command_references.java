package db.migration;

import org.flywaydb.core.api.migration.BaseJavaMigration;
import org.flywaydb.core.api.migration.Context;

import java.sql.Statement;

/** Keeps action plan command correlation aligned after outbox deduplication. */
public class V5__Reconcile_action_plan_command_references extends BaseJavaMigration {

    @Override
    public void migrate(Context context) throws Exception {
        try (Statement statement = context.getConnection().createStatement()) {
            statement.executeUpdate(
                    "UPDATE action_plans ap "
                            + "JOIN command_outbox co ON co.plan_id = ap.plan_id "
                            + "SET ap.command_id = co.command_id "
                            + "WHERE ap.command_id IS NULL OR ap.command_id <> co.command_id");
        }
    }
}
