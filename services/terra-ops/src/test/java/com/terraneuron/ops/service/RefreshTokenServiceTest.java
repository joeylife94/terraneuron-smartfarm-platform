package com.terraneuron.ops.service;

import com.terraneuron.ops.entity.RefreshTokenSession;
import com.terraneuron.ops.repository.RefreshTokenSessionRepository;
import com.terraneuron.ops.security.JwtTokenProvider;
import com.terraneuron.ops.security.JwtTokenProvider.GeneratedRefreshToken;
import com.terraneuron.ops.security.JwtTokenProvider.RefreshTokenClaims;
import com.terraneuron.ops.service.UserAuthenticationService.AuthenticatedUser;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class RefreshTokenServiceTest {

    private JwtTokenProvider tokenProvider;
    private RefreshTokenSessionRepository sessionRepository;
    private UserAuthenticationService authenticationService;
    private RefreshTokenService service;

    @BeforeEach
    void setUp() {
        tokenProvider = mock(JwtTokenProvider.class);
        sessionRepository = mock(RefreshTokenSessionRepository.class);
        authenticationService = mock(UserAuthenticationService.class);
        service = new RefreshTokenService(tokenProvider, sessionRepository, authenticationService);
    }

    @Test
    void rotatesOneActiveTokenAndPersistsItsReplacement() {
        String rawToken = "signed-refresh-token";
        Instant issuedAt = Instant.now().minusSeconds(10);
        Instant expiresAt = Instant.now().plusSeconds(600);
        RefreshTokenClaims claims = new RefreshTokenClaims(
                "admin", "token-1", "family-1", issuedAt, expiresAt);
        RefreshTokenSession current = activeSession(rawToken, claims);
        GeneratedRefreshToken replacement = new GeneratedRefreshToken(
                "replacement-token",
                "token-2",
                "family-1",
                Instant.now(),
                Instant.now().plusSeconds(600));
        AuthenticatedUser user = new AuthenticatedUser("admin", List.of("ROLE_ADMIN"));

        when(tokenProvider.parseRefreshToken(rawToken)).thenReturn(Optional.of(claims));
        when(sessionRepository.findByTokenIdForUpdate("token-1")).thenReturn(Optional.of(current));
        when(authenticationService.findEnabledByUsername("admin")).thenReturn(Optional.of(user));
        when(tokenProvider.generateRefreshTokenSession("admin", "family-1")).thenReturn(replacement);

        RefreshTokenService.RotationResult result = service.rotate(rawToken).orElseThrow();

        assertThat(result.user()).isEqualTo(user);
        assertThat(result.refreshToken()).isEqualTo("replacement-token");
        assertThat(current.getRevokeReason()).isEqualTo(RefreshTokenService.REASON_ROTATED);
        assertThat(current.getReplacedByTokenId()).isEqualTo("token-2");
        assertThat(current.getRevokedAt()).isNotNull();
        verify(sessionRepository).save(current);
        verify(sessionRepository).save(any(RefreshTokenSession.class));
        verify(sessionRepository, never()).revokeActiveFamily(any(), any(), any());
    }

    @Test
    void reuseOfRotatedTokenRevokesTheRemainingFamily() {
        String rawToken = "already-used-token";
        Instant issuedAt = Instant.now().minusSeconds(30);
        Instant expiresAt = Instant.now().plusSeconds(600);
        RefreshTokenClaims claims = new RefreshTokenClaims(
                "admin", "token-1", "family-1", issuedAt, expiresAt);
        RefreshTokenSession current = activeSession(rawToken, claims);
        current.revoke(Instant.now().minusSeconds(5), RefreshTokenService.REASON_ROTATED, "token-2");

        when(tokenProvider.parseRefreshToken(rawToken)).thenReturn(Optional.of(claims));
        when(sessionRepository.findByTokenIdForUpdate("token-1")).thenReturn(Optional.of(current));

        assertThat(service.rotate(rawToken)).isEmpty();

        verify(sessionRepository).revokeActiveFamily(
                eq("family-1"),
                any(Instant.class),
                eq(RefreshTokenService.REASON_REUSE_DETECTED));
        verify(authenticationService, never()).findEnabledByUsername(any());
    }

    @Test
    void disabledAccountRevokesTheWholeFamilyBeforeReplacement() {
        String rawToken = "active-token";
        Instant issuedAt = Instant.now().minusSeconds(10);
        Instant expiresAt = Instant.now().plusSeconds(600);
        RefreshTokenClaims claims = new RefreshTokenClaims(
                "disabled", "token-1", "family-1", issuedAt, expiresAt);
        RefreshTokenSession current = activeSession(rawToken, claims);

        when(tokenProvider.parseRefreshToken(rawToken)).thenReturn(Optional.of(claims));
        when(sessionRepository.findByTokenIdForUpdate("token-1")).thenReturn(Optional.of(current));
        when(authenticationService.findEnabledByUsername("disabled")).thenReturn(Optional.empty());

        assertThat(service.rotate(rawToken)).isEmpty();

        verify(sessionRepository).revokeActiveFamily(
                eq("family-1"),
                any(Instant.class),
                eq(RefreshTokenService.REASON_ACCOUNT_UNAVAILABLE));
        verify(tokenProvider, never()).generateRefreshTokenSession(any(), any());
    }

    @Test
    void logoutRevokesOnlyThePresentedActiveToken() {
        String rawToken = "logout-token";
        Instant issuedAt = Instant.now().minusSeconds(10);
        Instant expiresAt = Instant.now().plusSeconds(600);
        RefreshTokenClaims claims = new RefreshTokenClaims(
                "operator", "token-1", "family-1", issuedAt, expiresAt);
        RefreshTokenSession current = activeSession(rawToken, claims);

        when(tokenProvider.parseRefreshToken(rawToken)).thenReturn(Optional.of(claims));
        when(sessionRepository.findByTokenIdForUpdate("token-1")).thenReturn(Optional.of(current));

        service.revoke(rawToken);

        assertThat(current.getRevokeReason()).isEqualTo(RefreshTokenService.REASON_LOGOUT);
        assertThat(current.getRevokedAt()).isNotNull();
        verify(sessionRepository).save(current);
        verify(sessionRepository, never()).revokeActiveFamily(any(), any(), any());
    }

    @Test
    void mismatchedPersistedHashRevokesTheFamily() {
        String rawToken = "presented-token";
        Instant issuedAt = Instant.now().minusSeconds(10);
        Instant expiresAt = Instant.now().plusSeconds(600);
        RefreshTokenClaims claims = new RefreshTokenClaims(
                "admin", "token-1", "family-1", issuedAt, expiresAt);
        RefreshTokenSession current = activeSession("different-token", claims);

        when(tokenProvider.parseRefreshToken(rawToken)).thenReturn(Optional.of(claims));
        when(sessionRepository.findByTokenIdForUpdate("token-1")).thenReturn(Optional.of(current));

        assertThat(service.rotate(rawToken)).isEmpty();

        verify(sessionRepository).revokeActiveFamily(
                eq("family-1"),
                any(Instant.class),
                eq(RefreshTokenService.REASON_INTEGRITY_FAILURE));
    }

    private RefreshTokenSession activeSession(String rawToken, RefreshTokenClaims claims) {
        return RefreshTokenSession.builder()
                .tokenId(claims.tokenId())
                .tokenHash(RefreshTokenService.hash(rawToken))
                .username(claims.username())
                .familyId(claims.familyId())
                .issuedAt(claims.issuedAt())
                .expiresAt(claims.expiresAt())
                .build();
    }
}
