package db.migration;

import org.flywaydb.core.api.migration.BaseJavaMigration;
import org.flywaydb.core.api.migration.Context;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

/** Adds retryable safety-block metadata and one-command-per-plan enforcement. */
public class V4__Add_device_safety_gate_state extends BaseJavaMigration {

    private static final String UNIQUE_OUTBOX_PLAN_INDEX = "uk_outbox_plan_id";

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
        addUniqueIndexIfMissing(
                connection,
                "command_outbox",
                UNIQUE_OUTBOX_PLAN_INDEX,
                "plan_id");
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

    private static void addUniqueIndexIfMissing(
            Connection connection,
            String table,
            String index,
            String column) throws SQLException {
        if (indexExists(connection, table, index)) {
            return;
        }
        try (Statement statement = connection.createStatement()) {
            statement.execute(
                    "ALTER TABLE `" + table + "` ADD UNIQUE INDEX `" + index + "` (`" + column + "`)");
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

    private static boolean indexExists(
            Connection connection,
            String table,
            String index) throws SQLException {
        String sql = """
                SELECT 1
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = ?
                  AND INDEX_NAME = ?
                """;
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, table);
            statement.setString(2, index);
            try (ResultSet result = statement.executeQuery()) {
                return result.next();
            }
        }
    }
}
