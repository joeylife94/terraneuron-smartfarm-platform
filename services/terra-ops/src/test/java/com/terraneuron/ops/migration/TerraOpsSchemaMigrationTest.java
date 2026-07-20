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
import java.sql.DatabaseMetaData;
import java.sql.DriverManager;
import java.sql.ResultSet;
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

        assertThat(freshResult.migrationsExecuted).isEqualTo(6);
        assertThat(appliedVersions(fresh)).containsExactly("1", "2", "3", "4", "5", "6");
        assertCoreSchema();

        fresh.clean();
        try (Connection connection = connection()) {
            ScriptUtils.executeSqlScript(
                    connection,
                    new ClassPathResource("db/legacy/V0__pre_flyway_action_plans.sql"));
        }

        Flyway legacy = productionFlyway();
        MigrateResult legacyResult = legacy.migrate();

        assertThat(legacyResult.migrationsExecuted).isEqualTo(6);
        assertThat(appliedVersions(legacy)).containsExactly("0", "1", "2", "3", "4", "5", "6");
        assertCoreSchema();
        assertThat(legacy.migrate().migrationsExecuted).isZero();

        Flyway compose = composeFlyway();
        assertThat(compose.migrate().migrationsExecuted).isEqualTo(1);
        assertThat(compose.migrate().migrationsExecuted).isZero();
    }

    private static void assertCoreSchema() throws Exception {
        assertThat(tableExists("action_plans")).isTrue();
        assertThat(tableExists("command_outbox")).isTrue();
        assertThat(tableExists("refresh_token_sessions")).isTrue();
        assertThat(columnExists("action_plans", "command_id")).isTrue();
        assertThat(columnExists("action_plans", "ack_deadline_at")).isTrue();
        assertThat(columnExists("action_plans", "safety_block_reason_code")).isTrue();
        assertThat(columnExists("action_plans", "safety_blocked_at")).isTrue();
        assertThat(columnExists("refresh_token_sessions", "token_hash")).isTrue();
        assertThat(columnExists("refresh_token_sessions", "family_id")).isTrue();
        assertThat(columnExists("refresh_token_sessions", "revoked_at")).isTrue();
        assertThat(indexExists("action_plans", "idx_plan_command_id")).isTrue();
        assertThat(indexExists("command_outbox", "uk_outbox_plan_id")).isTrue();
        assertThat(indexExists("refresh_token_sessions", "uk_refresh_token_id")).isTrue();
        assertThat(indexExists("refresh_token_sessions", "uk_refresh_token_hash")).isTrue();
        assertThat(indexExists("refresh_token_sessions", "idx_refresh_family")).isTrue();
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
        try (Connection connection = connection()) {
            DatabaseMetaData metadata = connection.getMetaData();
            try (ResultSet result = metadata.getTables(
                    connection.getCatalog(), null, table, new String[]{"TABLE"})) {
                return result.next();
            }
        }
    }

    private static boolean columnExists(String table, String column) throws Exception {
        try (Connection connection = connection()) {
            DatabaseMetaData metadata = connection.getMetaData();
            try (ResultSet result = metadata.getColumns(
                    connection.getCatalog(), null, table, column)) {
                return result.next();
            }
        }
    }

    private static boolean indexExists(String table, String index) throws Exception {
        try (Connection connection = connection()) {
            DatabaseMetaData metadata = connection.getMetaData();
            try (ResultSet result = metadata.getIndexInfo(
                    connection.getCatalog(), null, table, false, false)) {
                while (result.next()) {
                    if (index.equals(result.getString("INDEX_NAME"))) {
                        return true;
                    }
                }
                return false;
            }
        }
    }

    private static Connection connection() throws Exception {
        return DriverManager.getConnection(
                MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword());
    }
}
