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
    private static final String OUTBOX_ARCHIVE_TABLE = "command_outbox_dedup_archive";
    private static final String OUTBOX_LOSER_TABLE = "tmp_command_outbox_dedup_losers";
    private static final String ARCHIVE_REASON = "DUPLICATE_PLAN_ID_BEFORE_UNIQUE_CONSTRAINT";

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

        if (!indexExists(connection, "command_outbox", UNIQUE_OUTBOX_PLAN_INDEX)) {
            archiveAndRemoveDuplicateOutboxRows(connection);
            verifyNoDuplicatePlanIds(connection);
            addUniqueIndexIfMissing(
                    connection,
                    "command_outbox",
                    UNIQUE_OUTBOX_PLAN_INDEX,
                    "plan_id");
        }
    }

    /**
     * Older releases allowed multiple outbox rows per plan. Preserve the strongest
     * lifecycle truth first: PUBLISHED and DEAD always outrank live retry rows,
     * even when action_plans.command_id still points at a PENDING or PROCESSING
     * duplicate. The command reference is only a tie-breaker between rows of the
     * same lifecycle strength, followed by the newest row. All removed rows are
     * copied to a durable archive table before deletion.
     */
    private static void archiveAndRemoveDuplicateOutboxRows(Connection connection)
            throws SQLException {
        if (!hasDuplicatePlanIds(connection)) {
            return;
        }

        createArchiveTableIfMissing(connection);
        dropTemporaryLoserTable(connection);
        execute(connection, "CREATE TEMPORARY TABLE `" + OUTBOX_LOSER_TABLE
                + "` (`id` BIGINT NOT NULL PRIMARY KEY)");
        execute(connection, """
                INSERT INTO `%s` (`id`)
                SELECT ranked.id
                FROM (
                    SELECT co.id,
                           ROW_NUMBER() OVER (
                               PARTITION BY co.plan_id
                               ORDER BY
                                   CASE co.status
                                       WHEN 'PUBLISHED' THEN 0
                                       WHEN 'DEAD' THEN 1
                                       WHEN 'PROCESSING' THEN 2
                                       WHEN 'PENDING' THEN 3
                                       ELSE 4
                                   END,
                                   CASE WHEN ap.command_id = co.command_id THEN 0 ELSE 1 END,
                                   co.id DESC
                           ) AS row_rank
                    FROM command_outbox co
                    LEFT JOIN action_plans ap ON ap.plan_id = co.plan_id
                ) ranked
                WHERE ranked.row_rank > 1
                """.formatted(OUTBOX_LOSER_TABLE));

        execute(connection, """
                INSERT IGNORE INTO `%s` (
                    id, event_id, plan_id, command_id, topic, message_key, payload,
                    status, attempts, next_attempt_at, locked_at, published_at,
                    last_error, version, created_at, updated_at,
                    archived_at, archive_reason
                )
                SELECT co.id, co.event_id, co.plan_id, co.command_id, co.topic,
                       co.message_key, co.payload, co.status, co.attempts,
                       co.next_attempt_at, co.locked_at, co.published_at,
                       co.last_error, co.version, co.created_at, co.updated_at,
                       CURRENT_TIMESTAMP(6), '%s'
                FROM command_outbox co
                INNER JOIN `%s` losers ON losers.id = co.id
                """.formatted(OUTBOX_ARCHIVE_TABLE, ARCHIVE_REASON, OUTBOX_LOSER_TABLE));

        execute(connection, "DELETE co FROM command_outbox co INNER JOIN `"
                + OUTBOX_LOSER_TABLE + "` losers ON losers.id = co.id");
        dropTemporaryLoserTable(connection);
    }

    private static void createArchiveTableIfMissing(Connection connection) throws SQLException {
        if (!tableExists(connection, OUTBOX_ARCHIVE_TABLE)) {
            execute(connection, "CREATE TABLE `" + OUTBOX_ARCHIVE_TABLE
                    + "` LIKE `command_outbox`");
        }
        addColumnIfMissing(
                connection,
                OUTBOX_ARCHIVE_TABLE,
                "archived_at",
                "DATETIME(6) NULL");
        addColumnIfMissing(
                connection,
                OUTBOX_ARCHIVE_TABLE,
                "archive_reason",
                "VARCHAR(64) NULL");
    }

    private static void verifyNoDuplicatePlanIds(Connection connection) throws SQLException {
        if (hasDuplicatePlanIds(connection)) {
            throw new SQLException(
                    "command_outbox still contains duplicate plan_id values after archival");
        }
    }

    private static boolean hasDuplicatePlanIds(Connection connection) throws SQLException {
        String sql = """
                SELECT 1
                FROM command_outbox
                GROUP BY plan_id
                HAVING COUNT(*) > 1
                LIMIT 1
                """;
        try (Statement statement = connection.createStatement();
             ResultSet result = statement.executeQuery(sql)) {
            return result.next();
        }
    }

    private static void dropTemporaryLoserTable(Connection connection) throws SQLException {
        execute(connection, "DROP TEMPORARY TABLE IF EXISTS `" + OUTBOX_LOSER_TABLE + "`");
    }

    private static void addColumnIfMissing(
            Connection connection,
            String table,
            String column,
            String definition) throws SQLException {
        if (columnExists(connection, table, column)) {
            return;
        }
        execute(connection,
                "ALTER TABLE `" + table + "` ADD COLUMN `" + column + "` " + definition);
    }

    private static void addUniqueIndexIfMissing(
            Connection connection,
            String table,
            String index,
            String column) throws SQLException {
        if (indexExists(connection, table, index)) {
            return;
        }
        execute(connection,
                "ALTER TABLE `" + table + "` ADD UNIQUE INDEX `" + index
                        + "` (`" + column + "`)");
    }

    private static boolean tableExists(Connection connection, String table) throws SQLException {
        String sql = """
                SELECT 1
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = ?
                """;
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, table);
            try (ResultSet result = statement.executeQuery()) {
                return result.next();
            }
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

    private static void execute(Connection connection, String sql) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute(sql);
        }
    }
}
