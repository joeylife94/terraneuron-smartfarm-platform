package db.migration;

import org.flywaydb.core.api.migration.BaseJavaMigration;
import org.flywaydb.core.api.migration.Context;

import java.sql.Statement;

/** Keeps action plan command correlation and lifecycle aligned after outbox deduplication. */
public class V5__Reconcile_action_plan_command_references extends BaseJavaMigration {

    @Override
    public void migrate(Context context) throws Exception {
        try (Statement statement = context.getConnection().createStatement()) {
            statement.executeUpdate(
                    "UPDATE action_plans ap "
                            + "JOIN command_outbox co ON co.plan_id = ap.plan_id "
                            + "SET ap.command_id = co.command_id "
                            + "WHERE ap.command_id IS NULL OR ap.command_id <> co.command_id");

            statement.executeUpdate(
                    "UPDATE action_plans ap "
                            + "JOIN command_outbox co ON co.plan_id = ap.plan_id "
                            + "SET ap.status = 'DISPATCHED', "
                            + "ap.dispatched_at = COALESCE(ap.dispatched_at, co.published_at, co.updated_at, co.created_at), "
                            + "ap.execution_result = 'KAFKA_ACKNOWLEDGED', "
                            + "ap.execution_error = NULL "
                            + "WHERE co.status = 'PUBLISHED' "
                            + "AND ap.status IN ('PENDING', 'APPROVED', 'SAFETY_BLOCKED', "
                            + "'DISPATCHING', 'DISPATCH_FAILED')");

            statement.executeUpdate(
                    "UPDATE action_plans ap "
                            + "JOIN command_outbox co ON co.plan_id = ap.plan_id "
                            + "SET ap.status = 'DISPATCH_FAILED', "
                            + "ap.execution_result = 'OUTBOX_DEAD_LETTER', "
                            + "ap.execution_error = COALESCE(co.last_error, ap.execution_error, "
                            + "'Legacy outbox delivery failed') "
                            + "WHERE co.status = 'DEAD' "
                            + "AND ap.status IN ('PENDING', 'APPROVED', 'SAFETY_BLOCKED', "
                            + "'DISPATCHING', 'DISPATCHED', 'DISPATCH_FAILED')");

            statement.executeUpdate(
                    "UPDATE action_plans ap "
                            + "JOIN command_outbox co ON co.plan_id = ap.plan_id "
                            + "SET ap.status = 'DISPATCHING', "
                            + "ap.execution_result = 'KAFKA_RETRY_PENDING', "
                            + "ap.execution_error = co.last_error "
                            + "WHERE co.status IN ('PENDING', 'PROCESSING') "
                            + "AND ap.status IN ('PENDING', 'APPROVED', 'SAFETY_BLOCKED')");
        }
    }
}
