package com.terraneuron.ops.service;

import com.terraneuron.ops.entity.RefreshTokenSession;
import com.terraneuron.ops.repository.RefreshTokenSessionRepository;
import com.terraneuron.ops.security.JwtTokenProvider;
import com.terraneuron.ops.security.JwtTokenProvider.GeneratedRefreshToken;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class RefreshTokenIssueTest {

    @Test
    void issueStoresOnlyDigestAndReturnsRawTokenOnce() {
        JwtTokenProvider provider = mock(JwtTokenProvider.class);
        RefreshTokenSessionRepository repository = mock(RefreshTokenSessionRepository.class);
        RefreshTokenService service = new RefreshTokenService(
                provider,
                repository,
                mock(UserAuthenticationService.class));
        GeneratedRefreshToken generated = new GeneratedRefreshToken(
                "raw-refresh-token",
                "token-id",
                "family-id",
                Instant.now(),
                Instant.now().plusSeconds(600));
        when(provider.generateRefreshTokenSession("admin")).thenReturn(generated);

        RefreshTokenService.IssuedRefreshToken issued = service.issue("admin");

        ArgumentCaptor<RefreshTokenSession> captor = ArgumentCaptor.forClass(RefreshTokenSession.class);
        verify(repository).save(captor.capture());
        assertThat(issued.token()).isEqualTo("raw-refresh-token");
        assertThat(captor.getValue().getTokenHash())
                .isEqualTo(RefreshTokenService.hash("raw-refresh-token"));
        assertThat(captor.getValue().toString()).doesNotContain("raw-refresh-token");
    }
}
