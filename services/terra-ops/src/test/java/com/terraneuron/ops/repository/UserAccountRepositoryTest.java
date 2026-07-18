package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.UserAccount;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.TestPropertySource;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@TestPropertySource(properties = {
        "spring.jpa.properties.hibernate.dialect=org.hibernate.dialect.H2Dialect",
        "spring.flyway.enabled=false",
        "spring.jpa.hibernate.ddl-auto=create-drop"
})
class UserAccountRepositoryTest {

    @Autowired
    private UserAccountRepository userRepository;

    @Test
    void persistsAndLoadsAuthenticationFieldsWithoutLoggingPasswordHash() {
        UserAccount saved = userRepository.saveAndFlush(UserAccount.builder()
                .username("operator")
                .passwordHash("$2b$12$secret-hash-must-not-be-logged")
                .email("operator@terraneuron.io")
                .fullName("Farm Operator")
                .roles("ROLE_OPERATOR")
                .enabled(true)
                .build());

        UserAccount loaded = userRepository.findByUsername("operator").orElseThrow();

        assertThat(loaded.getId()).isEqualTo(saved.getId());
        assertThat(loaded.getRoles()).isEqualTo("ROLE_OPERATOR");
        assertThat(loaded.isEnabled()).isTrue();
        assertThat(loaded.getCreatedAt()).isNotNull();
        assertThat(loaded.toString()).doesNotContain("secret-hash");
    }
}
