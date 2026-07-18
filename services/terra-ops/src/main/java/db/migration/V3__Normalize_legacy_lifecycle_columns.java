package db.migration;

import org.flywaydb.core.api.migration.BaseJavaMigration;
import org.flywaydb.core.api.migration.Context;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

/**
 * Normalizes lifecycle columns that Hibernate 6 may have created as native
 * MySQL ENUM while Terra-Ops still used ddl-auto=update.
 *
 * MySQL DDL auto-commits. Each conversion is conditional and preserves the
 * stored string value so the migration is safe to retry after operator repair.
 */
public class V3__Normalize_legacy_lifecycle_columns extends BaseJavaMigration {

    @Override
    public boolean canExecuteInTransaction() {
        return false;
    }

    @Override
    public void migrate(Context context) throws Exception {
        Connection connection = context.getConnection();

        normalizeEnumIfPresent(
                connection,
                "action_plans",
                "status",
                "VARCHAR(20) NOT NULL DEFAULT 'PENDING'"
        );
        normalizeEnumIfPresent(
                connection,
                "action_plans",
                "priority",
                "VARCHAR(20) NOT NULL DEFAULT 'MEDIUM'"
        );
        normalizeEnumIfPresent(
                connection,
                "audit_logs",
                "event_type",
                "VARCHAR(30) NOT NULL"
        );
        normalizeEnumIfPresent(
                connection,
                "command_outbox",
                "status",
                "VARCHAR(20) NOT NULL DEFAULT 'PENDING'"
        );
    }

    private static void normalizeEnumIfPresent(
            Connection connection,
            String table,
            String column,
            String definition
    ) throws SQLException {
        String dataType = columnDataType(connection, table, column);
        if (!"enum".equalsIgnoreCase(dataType)) {
            return;
        }

        execute(
                connection,
                "ALTER TABLE `" + table + "` MODIFY COLUMN `" + column + "` " + definition
        );
    }

    private static String columnDataType(
            Connection connection,
            String table,
            String column
    ) throws SQLException {
        String sql = """
                SELECT DATA_TYPE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = ?
                  AND COLUMN_NAME = ?
                """;
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, table);
            statement.setString(2, column);
            try (ResultSet result = statement.executeQuery()) {
                return result.next() ? result.getString(1) : null;
            }
        }
    }

    private static void execute(Connection connection, String sql) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute(sql);
        }
    }
}
