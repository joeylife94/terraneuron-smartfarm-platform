package db.migration;

import org.flywaydb.core.api.migration.BaseJavaMigration;
import org.flywaydb.core.api.migration.Context;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

/**
 * Adopts databases that were previously managed by init.sql plus Hibernate update.
 * MySQL DDL auto-commits, so every operation is additive and safe to retry after
 * an operator repairs a failed migration.
 */
public class V2__Reconcile_legacy_terra_ops_schema extends BaseJavaMigration {

    @Override
    public boolean canExecuteInTransaction() {
        return false;
    }

    @Override
    public void migrate(Context context) throws Exception {
        Connection connection = context.getConnection();

        addColumnIfMissing(connection, "action_plans", "command_id", "VARCHAR(50) NULL");
        addColumnIfMissing(connection, "action_plans", "dispatched_at", "DATETIME(6) NULL");
        addColumnIfMissing(connection, "action_plans", "delivered_at", "DATETIME(6) NULL");
        addColumnIfMissing(connection, "action_plans", "ack_deadline_at", "DATETIME(6) NULL");

        addIndexIfMissing(connection, "action_plans", "idx_plan_command_id", "command_id");
        addIndexIfMissing(connection, "action_plans", "idx_plan_ack_deadline", "ack_deadline_at");
    }

    private static void addColumnIfMissing(
            Connection connection,
            String table,
            String column,
            String definition
    ) throws SQLException {
        if (metadataExists(connection, "COLUMNS", "COLUMN_NAME", table, column)) {
            return;
        }
        execute(connection, "ALTER TABLE `" + table + "` ADD COLUMN `" + column + "` " + definition);
    }

    private static void addIndexIfMissing(
            Connection connection,
            String table,
            String index,
            String column
    ) throws SQLException {
        if (metadataExists(connection, "STATISTICS", "INDEX_NAME", table, index)) {
            return;
        }
        execute(connection, "CREATE INDEX `" + index + "` ON `" + table + "` (`" + column + "`)");
    }

    private static boolean metadataExists(
            Connection connection,
            String metadataTable,
            String nameColumn,
            String table,
            String name
    ) throws SQLException {
        String sql = "SELECT 1 FROM information_schema." + metadataTable
                + " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND " + nameColumn + " = ?";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, table);
            statement.setString(2, name);
            try (ResultSet result = statement.executeQuery()) {
                return result.next();
            }
        }
    }

    private static void execute(Connection connection, String sql) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute(sql);
        }
    }
}
