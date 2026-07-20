package com.terraneuron.ops.migration;

import org.flywaydb.core.Flyway;
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

import static org.assertj.core.api.Assertions.assertThat;

@Testcontainers(disabledWithoutDocker = true)
class TerraOpsDeadOutboxMigrationTest {

    @Container
    private static final MySQLContainer<?> MYSQL = new MySQLContainer<>("mysql:8.0")
            .withDatabaseName("terra_ops")
            .withUsername("terra")
            .withPassword("terra2025");

    @Test
    void terminalRowOutranksReferencedLiveRetryDuringLegacyDeduplication() throws Exception {
        try (Connection connection = connection()) {
            ScriptUtils.executeSqlScript(
                    connection,
                    new ClassPathResource("db/legacy/V0__pre_flyway_action_plans.sql"));
        }

        // Reproduce an upgraded database immediately before V4. V2 introduced
        // action_plans.command_id; legacy runtime state can point it at a live retry
        // even though another duplicate row already contains terminal DEAD truth.
        flywayThroughVersion3().migrate();
        execute("UPDATE action_plans "
                + "SET command_id = 'legacy-command-retry' "
                + "WHERE plan_id = 'legacy-dead-plan'");
        assertThat(scalar("SELECT command_id FROM action_plans "
                + "WHERE plan_id = 'legacy-dead-plan'"))
                .isEqualTo("legacy-command-retry");

        productionFlyway().migrate();

        assertThat(scalar("SELECT COUNT(*) FROM command_outbox "
                + "WHERE plan_id = 'legacy-dead-plan'"))
                .isEqualTo("1");
        assertThat(scalar("SELECT command_id FROM command_outbox "
                + "WHERE plan_id = 'legacy-dead-plan'"))
                .isEqualTo("legacy-command-dead");
        assertThat(scalar("SELECT status FROM command_outbox "
                + "WHERE plan_id = 'legacy-dead-plan'"))
                .isEqualTo("DEAD");
        assertThat(scalar("SELECT command_id FROM command_outbox_dedup_archive "
                + "WHERE plan_id = 'legacy-dead-plan'"))
                .isEqualTo("legacy-command-retry");
        assertThat(scalar("SELECT status FROM command_outbox_dedup_archive "
                + "WHERE plan_id = 'legacy-dead-plan'"))
                .isEqualTo("PENDING");
        assertThat(scalar("SELECT archive_reason FROM command_outbox_dedup_archive "
                + "WHERE plan_id = 'legacy-dead-plan'"))
                .isEqualTo("DUPLICATE_PLAN_ID_BEFORE_UNIQUE_CONSTRAINT");
    }

    private static Flyway flywayThroughVersion3() {
        return Flyway.configure()
                .dataSource(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword())
                .locations("classpath:db/migration")
                .baselineOnMigrate(true)
                .baselineVersion("0")
                .target("3")
                .load();
    }

    private static Flyway productionFlyway() {
        return Flyway.configure()
                .dataSource(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword())
                .locations("classpath:db/migration")
                .baselineOnMigrate(true)
                .baselineVersion("0")
                .load();
    }

    private static void execute(String sql) throws Exception {
        try (Connection connection = connection();
             Statement statement = connection.createStatement()) {
            statement.execute(sql);
        }
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
        return DriverManager.getConnection(
                MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword());
    }
}
