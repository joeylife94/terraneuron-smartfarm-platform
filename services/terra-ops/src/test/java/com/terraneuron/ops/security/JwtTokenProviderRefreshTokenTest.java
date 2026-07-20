package com.terraneuron.ops.security;

import com.terraneuron.ops.security.JwtTokenProvider.GeneratedRefreshToken;
import com.terraneuron.ops.security.JwtTokenProvider.RefreshTokenClaims;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;

class JwtTokenProviderRefreshTokenTest {

    private JwtTokenProvider tokenProvider;

    @BeforeEach
    void setUp() {
        tokenProvider = new JwtTokenProvider();
        ReflectionTestUtils.setField(
                tokenProvider,
                "jwtSecret",
                "test-refresh-secret-that-is-at-least-32-bytes-long");
        ReflectionTestUtils.setField(tokenProvider, "jwtExpiration", 60_000L);
        ReflectionTestUtils.setField(tokenProvider, "refreshExpiration", 600_000L);
        tokenProvider.validateJwtSecret();
    }

    @Test
    void generatesRequiredRefreshIdentityClaimsAndPreservesFamilyOnRotation() {
        GeneratedRefreshToken first = tokenProvider.generateRefreshTokenSession("admin");
        RefreshTokenClaims firstClaims = tokenProvider.parseRefreshToken(first.token()).orElseThrow();

        assertThat(firstClaims.username()).isEqualTo("admin");
        assertThat(firstClaims.tokenId()).isEqualTo(first.tokenId());
        assertThat(firstClaims.familyId()).isEqualTo(first.familyId());
        assertThat(tokenProvider.validateRefreshToken(first.token())).isTrue();
        assertThat(tokenProvider.validateAccessToken(first.token())).isFalse();

        GeneratedRefreshToken replacement = tokenProvider.generateRefreshTokenSession(
                "admin",
                first.familyId());

        assertThat(replacement.familyId()).isEqualTo(first.familyId());
        assertThat(replacement.tokenId()).isNotEqualTo(first.tokenId());
        assertThat(replacement.token()).isNotEqualTo(first.token());
    }

    @Test
    void rejectsAccessTokenAsRefreshToken() {
        String accessToken = tokenProvider.generateToken("admin", "ROLE_ADMIN");

        assertThat(tokenProvider.validateAccessToken(accessToken)).isTrue();
        assertThat(tokenProvider.parseRefreshToken(accessToken)).isEmpty();
    }
}
