package db.migration;

import org.flywaydb.core.api.migration.BaseJavaMigration;
import org.flywaydb.core.api.migration.Context;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

/** Adds retryable safety-block metadata without changing existing lifecycle values. */
public class V4__Add_device_safety_gate_state extends BaseJavaMigration {

    @Override
    public boolean canExecuteInTransaction() {
        return false;
    }

    @Override
    public void migrate(Context context) throws Exception {
        Connection connection = context.getConnection();
        addColumnIfMissing(
                connection,
                "action_plans",
                "safety_block_reason_code",
                "VARCHAR(64) NULL AFTER `rejection_reason`");
        addColumnIfMissing(
                connection,
                "action_plans",
                "safety_blocked_at",
                "DATETIME(6) NULL AFTER `safety_block_reason_code`");
    }

    private static void addColumnIfMissing(
            Connection connection,
            String table,
            String column,
            String definition) throws SQLException {
        if (columnExists(connection, table, column)) {
            return;
        }
        try (Statement statement = connection.createStatement()) {
            statement.execute(
                    "ALTER TABLE `" + table + "` ADD COLUMN `" + column + "` " + definition);
        }
    }

    private static boolean columnExists(
            Connection connection,
            String table,
            String column) throws SQLException {
        String sql = """
                SELECT 1
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = ?
                  AND COLUMN_NAME = ?
                """;
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, table);
            statement.setString(2, column);
            try (ResultSet result = statement.executeQuery()) {
                return result.next();
            }
        }
    }
}
