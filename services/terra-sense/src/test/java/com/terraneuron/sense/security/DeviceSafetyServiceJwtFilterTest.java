package com.terraneuron.sense.security;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.test.util.ReflectionTestUtils;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Date;

import static org.assertj.core.api.Assertions.assertThat;

class DeviceSafetyServiceJwtFilterTest {

    private static final String SECRET = "test-device-safety-secret-key-32-bytes-minimum";
    private static final Instant NOW = Instant.parse("2026-07-18T03:00:00Z");

    private DeviceSafetyServiceJwtFilter filter;

    @BeforeEach
    void setUp() {
        filter = new DeviceSafetyServiceJwtFilter(Clock.fixed(NOW, ZoneOffset.UTC));
        ReflectionTestUtils.setField(filter, "secret", SECRET);
        ReflectionTestUtils.setField(filter, "expectedIssuer", "terraneuron-internal");
        ReflectionTestUtils.setField(filter, "expectedAudience", "terra-sense");
        ReflectionTestUtils.setField(filter, "allowedSubject", "terra-ops");
        ReflectionTestUtils.setField(filter, "clockSkewSeconds", 5L);
        ReflectionTestUtils.setField(filter, "maxLifetimeSeconds", 60L);
        filter.validateConfiguration();
    }

    @AfterEach
    void clearContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void validSubjectAudienceScopeAndExpiryAuthenticateInternalEndpoint() throws Exception {
        MockHttpServletResponse response = invoke(
                "/internal/device-safety/evaluate",
                token("terra-ops", "terra-sense", "device:safety:evaluate", NOW.minusSeconds(1), NOW.plusSeconds(29)));

        assertThat(response.getStatus()).isEqualTo(200);
        assertThat(SecurityContextHolder.getContext().getAuthentication().getAuthorities())
                .extracting(Object::toString)
                .contains("SERVICE_TERRA_OPS", "SCOPE_device:safety:evaluate");
    }

    @Test
    void wrongSubjectAudienceScopeOrExpiredTokenIsRejected() throws Exception {
        assertThat(invoke("/internal/device-safety/evaluate",
                token("other", "terra-sense", "device:safety:evaluate", NOW, NOW.plusSeconds(30)))
                .getStatus()).isEqualTo(401);
        assertThat(invoke("/internal/device-safety/evaluate",
                token("terra-ops", "other", "device:safety:evaluate", NOW, NOW.plusSeconds(30)))
                .getStatus()).isEqualTo(401);
        assertThat(invoke("/internal/device-safety/evaluate",
                token("terra-ops", "terra-sense", "device:read", NOW, NOW.plusSeconds(30)))
                .getStatus()).isEqualTo(401);
        assertThat(invoke("/internal/device-safety/evaluate",
                token("terra-ops", "terra-sense", "device:safety:evaluate", NOW.minusSeconds(90), NOW.minusSeconds(30)))
                .getStatus()).isEqualTo(401);
    }

    @Test
    void sameServiceTokenIsForbiddenOnOtherSenseApis() throws Exception {
        MockHttpServletResponse response = invoke(
                "/api/devices",
                token("terra-ops", "terra-sense", "device:safety:evaluate", NOW, NOW.plusSeconds(30)));

        assertThat(response.getStatus()).isEqualTo(403);
    }

    private MockHttpServletResponse invoke(String path, String token) throws Exception {
        SecurityContextHolder.clearContext();
        MockHttpServletRequest request = new MockHttpServletRequest("POST", path);
        request.addHeader("Authorization", "Bearer " + token);
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilterInternal(request, response, new MockFilterChain());
        return response;
    }

    private String token(
            String subject,
            String audience,
            String scope,
            Instant issuedAt,
            Instant expiration) {
        return Jwts.builder()
                .issuer("terraneuron-internal")
                .subject(subject)
                .audience().add(audience).and()
                .claim("type", "service")
                .claim("scope", scope)
                .issuedAt(Date.from(issuedAt))
                .expiration(Date.from(expiration))
                .signWith(signingKey())
                .compact();
    }

    private SecretKey signingKey() {
        return Keys.hmacShaKeyFor(SECRET.getBytes(StandardCharsets.UTF_8));
    }
}
