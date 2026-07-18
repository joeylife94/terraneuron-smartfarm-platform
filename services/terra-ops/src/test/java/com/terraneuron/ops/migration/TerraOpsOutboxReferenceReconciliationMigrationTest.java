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
class TerraOpsOutboxReferenceReconciliationMigrationTest {

    @Container
    private static final MySQLContainer<?> MYSQL = new MySQLContainer<>("mysql:8.0")
            .withDatabaseName("terra_ops")
            .withUsername("terra")
            .withPassword("terra2025");

    @Test
    void planCommandReferenceTracksTheOutboxRowPreservedByDeduplication() throws Exception {
        try (Connection connection = connection()) {
            ScriptUtils.executeSqlScript(
                    connection,
                    new ClassPathResource("db/legacy/V0__pre_flyway_action_plans.sql"));
        }

        flywayThroughVersion3().migrate();
        execute("UPDATE action_plans "
                + "SET command_id = 'legacy-command-retry' "
                + "WHERE plan_id = 'legacy-dead-plan'");

        productionFlyway().migrate();

        assertThat(scalar("SELECT command_id FROM command_outbox "
                + "WHERE plan_id = 'legacy-dead-plan'"))
                .isEqualTo("legacy-command-dead");
        assertThat(scalar("SELECT command_id FROM action_plans "
                + "WHERE plan_id = 'legacy-dead-plan'"))
                .isEqualTo("legacy-command-dead");
        assertThat(scalar("SELECT COUNT(*) FROM action_plans "
                + "WHERE command_id = 'legacy-command-dead'"))
                .isEqualTo("1");
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
