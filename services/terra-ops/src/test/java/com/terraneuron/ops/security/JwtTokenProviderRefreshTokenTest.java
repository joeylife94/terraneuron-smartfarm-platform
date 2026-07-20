package com.terraneuron.ops.security;

import com.terraneuron.ops.security.JwtTokenProvider.GeneratedRefreshToken;
import com.terraneuron.ops.security.JwtTokenProvider.RefreshTokenClaims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.charset.StandardCharsets;
import java.util.Date;

import static org.assertj.core.api.Assertions.assertThat;

class JwtTokenProviderRefreshTokenTest {

    private static final String TEST_SECRET =
            "test-refresh-secret-that-is-at-least-32-bytes-long";

    private JwtTokenProvider tokenProvider;

    @BeforeEach
    void setUp() {
        tokenProvider = new JwtTokenProvider();
        ReflectionTestUtils.setField(tokenProvider, "jwtSecret", TEST_SECRET);
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
        assertThat(tokenProvider.parseRefreshTokenForRotation(accessToken)).isEmpty();
    }

    @Test
    void rejectsPreV6RefreshTokenWithoutServerSideIdentityClaims() {
        Date now = new Date();
        String legacyRefreshToken = Jwts.builder()
                .subject("admin")
                .claim("type", "refresh")
                .issuedAt(now)
                .expiration(new Date(now.getTime() + 600_000L))
                .signWith(Keys.hmacShaKeyFor(TEST_SECRET.getBytes(StandardCharsets.UTF_8)))
                .compact();

        assertThat(tokenProvider.validateToken(legacyRefreshToken)).isTrue();
        assertThat(tokenProvider.parseRefreshToken(legacyRefreshToken)).isEmpty();
        assertThat(tokenProvider.parseRefreshTokenForRotation(legacyRefreshToken)).isEmpty();
        assertThat(tokenProvider.validateRefreshToken(legacyRefreshToken)).isFalse();
    }

    @Test
    void exposesVerifiedIdentityOfExpiredRefreshTokenOnlyForReplayHandling() {
        Date issuedAt = new Date(System.currentTimeMillis() - 1_200_000L);
        Date expiresAt = new Date(System.currentTimeMillis() - 600_000L);
        String expiredRefreshToken = Jwts.builder()
                .id("11111111-1111-1111-1111-111111111111")
                .subject("admin")
                .claim("type", "refresh")
                .claim("family", "22222222-2222-2222-2222-222222222222")
                .issuedAt(issuedAt)
                .expiration(expiresAt)
                .signWith(Keys.hmacShaKeyFor(TEST_SECRET.getBytes(StandardCharsets.UTF_8)))
                .compact();

        assertThat(tokenProvider.parseRefreshToken(expiredRefreshToken)).isEmpty();
        assertThat(tokenProvider.validateRefreshToken(expiredRefreshToken)).isFalse();

        RefreshTokenClaims replayClaims = tokenProvider
                .parseRefreshTokenForRotation(expiredRefreshToken)
                .orElseThrow();
        assertThat(replayClaims.username()).isEqualTo("admin");
        assertThat(replayClaims.tokenId())
                .isEqualTo("11111111-1111-1111-1111-111111111111");
        assertThat(replayClaims.familyId())
                .isEqualTo("22222222-2222-2222-2222-222222222222");
        assertThat(replayClaims.expiresAt()).isBefore(java.time.Instant.now());
    }
}
