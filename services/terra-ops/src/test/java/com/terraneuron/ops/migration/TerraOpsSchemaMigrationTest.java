package com.terraneuron.ops.migration;

import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationInfo;
import org.flywaydb.core.api.output.MigrateResult;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.Arrays;

import static org.assertj.core.api.Assertions.assertThat;

@Testcontainers(disabledWithoutDocker = true)
class TerraOpsSchemaMigrationTest {

    @Container
    private static final MySQLContainer<?> MYSQL = new MySQLContainer<>("mysql:8.0")
            .withDatabaseName("terra_ops")
            .withUsername("terra")
            .withPassword("terra2025");

    @Test
    void supportsFreshInstallAndNonDestructiveLegacyAdoption() throws Exception {
        Flyway fresh = productionFlyway();
        MigrateResult freshResult = fresh.migrate();

        assertThat(freshResult.migrationsExecuted).isEqualTo(4);
        assertThat(appliedVersions(fresh)).containsExactly("1", "2", "3", "4");
        assertThat(tableExists("command_outbox")).isTrue();
        assertThat(columnExists("action_plans", "ack_deadline_at")).isTrue();
        assertThat(columnExists("action_plans", "safety_block_reason_code")).isTrue();
        assertThat(columnExists("action_plans", "safety_blocked_at")).isTrue();
        assertThat(indexExists("command_outbox", "uk_outbox_plan_id")).isTrue();
        assertThat(columnDataType("command_outbox", "status")).isEqualTo("varchar");
        assertThat(rowCount("users")).isZero();

        fresh.clean();
        try (Connection connection = connection()) {
            ScriptUtils.executeSqlScript(
                    connection,
                    new ClassPathResource("db/legacy/V0__pre_flyway_action_plans.sql"));
        }

        Flyway legacy = productionFlyway();
        MigrateResult legacyResult = legacy.migrate();

        assertThat(legacyResult.migrationsExecuted).isEqualTo(4);
        assertThat(appliedVersions(legacy)).containsExactly("0", "1", "2", "3", "4");
        assertThat(scalar("SELECT plan_id FROM action_plans WHERE plan_id = 'legacy-plan-preserved'"))
                .isEqualTo("legacy-plan-preserved");
        assertThat(columnExists("action_plans", "command_id")).isTrue();
        assertThat(columnExists("action_plans", "dispatched_at")).isTrue();
        assertThat(columnExists("action_plans", "delivered_at")).isTrue();
        assertThat(columnExists("action_plans", "ack_deadline_at")).isTrue();
        assertThat(columnExists("action_plans", "safety_block_reason_code")).isTrue();
        assertThat(columnExists("action_plans", "safety_blocked_at")).isTrue();
        assertThat(indexExists("action_plans", "idx_plan_command_id")).isTrue();
        assertThat(indexExists("command_outbox", "uk_outbox_plan_id")).isTrue();
        assertThat(tableExists("command_outbox")).isTrue();
        assertThat(columnDataType("action_plans", "status")).isEqualTo("varchar");
        assertThat(columnDataType("action_plans", "priority")).isEqualTo("varchar");
        assertThat(columnDataType("audit_logs", "event_type")).isEqualTo("varchar");
        assertThat(columnDataType("command_outbox", "status")).isEqualTo("varchar");
        assertThat(scalar("SELECT status FROM action_plans WHERE plan_id = 'legacy-plan-preserved'"))
                .isEqualTo("APPROVED");
        assertThat(scalar("SELECT priority FROM action_plans WHERE plan_id = 'legacy-plan-preserved'"))
                .isEqualTo("HIGH");
        assertThat(scalar("SELECT event_type FROM audit_logs WHERE log_id = 'legacy-log-preserved'"))
                .isEqualTo("PLAN_CREATED");
        assertThat(scalar("SELECT status FROM command_outbox WHERE command_id = 'legacy-command-preserved'"))
                .isEqualTo("PUBLISHED");
        assertThat(legacy.migrate().migrationsExecuted).isZero();

        Flyway compose = composeFlyway();
        assertThat(compose.migrate().migrationsExecuted).isEqualTo(1);
        assertThat(rowCount("users")).isEqualTo(3);
        assertThat(rowCount("crop_profiles")).isEqualTo(5);
        assertThat(rowCount("farm_crops")).isEqualTo(3);
        assertThat(compose.migrate().migrationsExecuted).isZero();
    }

    private static Flyway productionFlyway() {
        return flyway("classpath:db/migration");
    }

    private static Flyway composeFlyway() {
        return flyway("classpath:db/migration", "classpath:db/local");
    }

    private static Flyway flyway(String... locations) {
        return Flyway.configure()
                .dataSource(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword())
                .locations(locations)
                .baselineOnMigrate(true)
                .baselineVersion("0")
                .cleanDisabled(false)
                .load();
    }

    private static String[] appliedVersions(Flyway flyway) {
        return Arrays.stream(flyway.info().applied())
                .map(MigrationInfo::getVersion)
                .map(version -> version == null ? "repeatable" : version.getVersion())
                .toArray(String[]::new);
    }

    private static boolean tableExists(String table) throws Exception {
        return metadataExists("SELECT 1 FROM information_schema.TABLES "
                + "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '" + table + "'");
    }

    private static boolean columnExists(String table, String column) throws Exception {
        return metadataExists("SELECT 1 FROM information_schema.COLUMNS "
                + "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '" + table + "' "
                + "AND COLUMN_NAME = '" + column + "'");
    }

    private static String columnDataType(String table, String column) throws Exception {
        return scalar("SELECT DATA_TYPE FROM information_schema.COLUMNS "
                + "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '" + table + "' "
                + "AND COLUMN_NAME = '" + column + "'");
    }

    private static boolean indexExists(String table, String index) throws Exception {
        return metadataExists("SELECT 1 FROM information_schema.STATISTICS "
                + "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '" + table + "' "
                + "AND INDEX_NAME = '" + index + "'");
    }

    private static boolean metadataExists(String sql) throws Exception {
        try (Connection connection = connection();
             Statement statement = connection.createStatement();
             ResultSet result = statement.executeQuery(sql)) {
            return result.next();
        }
    }

    private static long rowCount(String table) throws Exception {
        return Long.parseLong(scalar("SELECT COUNT(*) FROM " + table));
    }

    private static String scalar(String sql) throws Exception {
        try (Connection connection = connection();
             Statement statement = connection.createStatement();
             ResultSet result = statement.executeQuery(sql)) {
            assertThat(result.next()).isTrue();
            return result.getString(1);
        }
    }

    private static Connection connection() throws Exception {
        return DriverManager.getConnection(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword());
    }
}
