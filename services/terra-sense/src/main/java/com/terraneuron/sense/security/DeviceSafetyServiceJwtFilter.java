package com.terraneuron.sense.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.annotation.PostConstruct;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.util.matcher.AntPathRequestMatcher;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.crypto.SecretKey;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Collection;
import java.util.Date;
import java.util.List;

/** Authenticates Terra-Ops only for the internal device-safety evaluation endpoint. */
@Slf4j
@Component
public class DeviceSafetyServiceJwtFilter extends OncePerRequestFilter {

    public static final String REQUIRED_SCOPE = "device:safety:evaluate";
    private static final AntPathRequestMatcher SAFETY_MATCHER =
            new AntPathRequestMatcher("/internal/device-safety/evaluate", "POST");

    private final Clock clock;

    @Value("${device-safety.service-auth.jwt.secret}")
    private String secret;

    @Value("${device-safety.service-auth.jwt.issuer:terraneuron-internal}")
    private String expectedIssuer;

    @Value("${device-safety.service-auth.jwt.audience:terra-sense}")
    private String expectedAudience;

    @Value("${device-safety.service-auth.jwt.allowed-subject:terra-ops}")
    private String allowedSubject;

    @Value("${device-safety.service-auth.jwt.clock-skew-seconds:5}")
    private long clockSkewSeconds;

    @Value("${device-safety.service-auth.jwt.max-lifetime-seconds:60}")
    private long maxLifetimeSeconds;

    public DeviceSafetyServiceJwtFilter(Clock clock) {
        this.clock = clock;
    }

    @PostConstruct
    void validateConfiguration() {
        if (!StringUtils.hasText(secret)
                || secret.getBytes(StandardCharsets.UTF_8).length < 32) {
            throw new IllegalStateException(
                    "DEVICE_SAFETY_JWT_SECRET is required and must be at least 32 bytes");
        }
        if (clockSkewSeconds < 0 || maxLifetimeSeconds <= 0) {
            throw new IllegalStateException("Device safety service JWT time limits are invalid");
        }
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {
        boolean safetyEndpoint = SAFETY_MATCHER.matches(request);
        String token = bearerToken(request);

        if (!StringUtils.hasText(token)) {
            if (safetyEndpoint) {
                unauthorized(response);
                return;
            }
            filterChain.doFilter(request, response);
            return;
        }

        try {
            Claims claims = parse(token);
            boolean serviceToken = "service".equals(claims.get("type", String.class));
            if (!safetyEndpoint) {
                if (serviceToken) {
                    response.sendError(HttpServletResponse.SC_FORBIDDEN);
                    return;
                }
                filterChain.doFilter(request, response);
                return;
            }

            validateClaims(claims);
            UsernamePasswordAuthenticationToken authentication =
                    new UsernamePasswordAuthenticationToken(
                            "service:" + claims.getSubject(),
                            null,
                            List.of(
                                    new SimpleGrantedAuthority("SERVICE_TERRA_OPS"),
                                    new SimpleGrantedAuthority("SCOPE_" + REQUIRED_SCOPE)));
            SecurityContextHolder.getContext().setAuthentication(authentication);
            filterChain.doFilter(request, response);
        } catch (Exception ex) {
            if (safetyEndpoint) {
                log.warn("Rejected device safety service token: {}", ex.getClass().getSimpleName());
                unauthorized(response);
                return;
            }
            // Tokens signed for another security domain, including user JWTs, are ignored here.
            filterChain.doFilter(request, response);
        }
    }

    private Claims parse(String token) {
        return Jwts.parser()
                .verifyWith(signingKey())
                .clock(() -> Date.from(clock.instant()))
                .clockSkewSeconds(clockSkewSeconds)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    private void validateClaims(Claims claims) {
        if (!expectedIssuer.equals(claims.getIssuer())) {
            throw new IllegalArgumentException("unexpected issuer");
        }
        if (!allowedSubject.equals(claims.getSubject())) {
            throw new IllegalArgumentException("unexpected subject");
        }
        if (!"service".equals(claims.get("type", String.class))) {
            throw new IllegalArgumentException("service token type required");
        }
        if (!audienceContains(claims.get("aud"))) {
            throw new IllegalArgumentException("unexpected audience");
        }
        if (!scopeContains(claims.get("scope"))) {
            throw new IllegalArgumentException("required scope missing");
        }

        Date issuedAt = claims.getIssuedAt();
        Date expiration = claims.getExpiration();
        if (issuedAt == null || expiration == null) {
            throw new IllegalArgumentException("issued-at and expiration required");
        }
        Instant now = clock.instant();
        if (issuedAt.toInstant().isAfter(now.plusSeconds(clockSkewSeconds))) {
            throw new IllegalArgumentException("issued-at is in the future");
        }
        Duration lifetime = Duration.between(issuedAt.toInstant(), expiration.toInstant());
        if (lifetime.isNegative() || lifetime.toSeconds() > maxLifetimeSeconds) {
            throw new IllegalArgumentException("service token lifetime exceeds policy");
        }
    }

    private boolean audienceContains(Object audienceClaim) {
        if (audienceClaim instanceof String audience) {
            return expectedAudience.equals(audience);
        }
        if (audienceClaim instanceof Collection<?> audiences) {
            return audiences.stream().anyMatch(expectedAudience::equals);
        }
        return false;
    }

    private boolean scopeContains(Object scopeClaim) {
        if (scopeClaim instanceof String scopes) {
            return List.of(scopes.split("\\s+")).contains(REQUIRED_SCOPE);
        }
        if (scopeClaim instanceof Collection<?> scopes) {
            return scopes.stream().anyMatch(REQUIRED_SCOPE::equals);
        }
        return false;
    }

    private SecretKey signingKey() {
        return Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }

    private String bearerToken(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        return StringUtils.hasText(header) && header.startsWith("Bearer ")
                ? header.substring(7)
                : null;
    }

    private void unauthorized(HttpServletResponse response) throws IOException {
        response.sendError(HttpServletResponse.SC_UNAUTHORIZED);
    }
}
