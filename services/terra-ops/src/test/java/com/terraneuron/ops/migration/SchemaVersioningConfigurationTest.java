package com.terraneuron.ops.migration;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

class SchemaVersioningConfigurationTest {

    @Test
    void productionUsesFlywayAndHibernateValidationWithoutDemoCredentials() throws Exception {
        String application = resource("application.properties");
        String productionMigration = resource("db/migration/V1__create_terra_ops_schema.sql");

        assertThat(application)
                .contains("spring.flyway.enabled=true")
                .contains("spring.flyway.locations=classpath:db/migration")
                .contains("spring.flyway.baseline-on-migrate=true")
                .contains("spring.flyway.baseline-version=0")
                .contains("spring.jpa.hibernate.ddl-auto=validate")
                .doesNotContain("ddl-auto=update");
        assertThat(productionMigration)
                .contains("CREATE TABLE IF NOT EXISTS command_outbox")
                .doesNotContain("$2b$", "INSERT INTO users");
    }

    @Test
    void composeExplicitlyOptsIntoLocalSeed() throws Exception {
        assertThat(resource("application-compose.properties"))
                .contains("classpath:db/migration,classpath:db/local");
        assertThat(resource("db/local/R__compose_seed.sql"))
                .contains("Local Docker Compose/E2E seed only")
                .contains("INSERT IGNORE INTO users");
    }

    private static String resource(String path) throws Exception {
        return new ClassPathResource(path).getContentAsString(StandardCharsets.UTF_8);
    }
}
