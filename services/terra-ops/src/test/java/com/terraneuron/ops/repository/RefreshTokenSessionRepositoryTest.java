package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.RefreshTokenSession;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.TestPropertySource;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@TestPropertySource(properties = {
        "spring.flyway.enabled=false",
        "spring.jpa.hibernate.ddl-auto=create-drop"
})
class RefreshTokenSessionRepositoryTest {

    @Autowired
    private RefreshTokenSessionRepository repository;

    @Test
    void persistsRotationAndRevocationMetadataWithoutRawToken() {
        RefreshTokenSession session = RefreshTokenSession.builder()
                .tokenId("11111111-1111-1111-1111-111111111111")
                .tokenHash("a".repeat(64))
                .username("admin")
                .familyId("22222222-2222-2222-2222-222222222222")
                .issuedAt(Instant.now())
                .expiresAt(Instant.now().plusSeconds(600))
                .build();

        RefreshTokenSession stored = repository.saveAndFlush(session);
        RefreshTokenSession locked = repository.findByTokenIdForUpdate(stored.getTokenId()).orElseThrow();
        locked.revoke(Instant.now(), "ROTATED", "33333333-3333-3333-3333-333333333333");
        repository.saveAndFlush(locked);

        RefreshTokenSession reloaded = repository.findById(stored.getId()).orElseThrow();
        assertThat(reloaded.getTokenHash()).isEqualTo("a".repeat(64));
        assertThat(reloaded.getRevokeReason()).isEqualTo("ROTATED");
        assertThat(reloaded.getReplacedByTokenId())
                .isEqualTo("33333333-3333-3333-3333-333333333333");
    }
}
