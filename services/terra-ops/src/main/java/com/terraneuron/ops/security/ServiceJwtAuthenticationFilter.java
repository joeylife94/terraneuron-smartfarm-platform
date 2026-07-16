package com.terraneuron.ops.security;

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
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.security.web.util.matcher.AntPathRequestMatcher;

import javax.crypto.SecretKey;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Collection;
import java.util.List;

/**
 * Authenticates Terra-Cortex only for the crop conditions endpoint.
 *
 * The filter deliberately does not authenticate service tokens on any other route. This keeps the
 * service credential scoped to one read-only integration boundary even though the rest of the API
 * contains routes that merely require an authenticated principal.
 */
@Slf4j
@Component
public class ServiceJwtAuthenticationFilter extends OncePerRequestFilter {

    static final String REQUIRED_SCOPE = "crop:read";
    private static final AntPathRequestMatcher CROP_CONDITIONS_MATCHER =
            new AntPathRequestMatcher("/api/farms/*/optimal-conditions", "GET");

    @Value("${service-auth.jwt.secret}")
    private String serviceJwtSecret;

    @Value("${service-auth.jwt.issuer:terraneuron-internal}")
    private String expectedIssuer;

    @Value("${service-auth.jwt.audience:terra-ops}")
    private String expectedAudience;

    @Value("${service-auth.jwt.allowed-subject:terra-cortex}")
    private String allowedSubject;

    @PostConstruct
    void validateConfiguration() {
        if (!StringUtils.hasText(serviceJwtSecret)) {
            throw new IllegalStateException("SERVICE_AUTH_JWT_SECRET is required and must not be blank.");
        }
        if (serviceJwtSecret.getBytes(StandardCharsets.UTF_8).length < 32) {
            throw new IllegalStateException(
                    "SERVICE_AUTH_JWT_SECRET must be at least 32 bytes for HMAC-SHA signing."
            );
        }
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !CROP_CONDITIONS_MATCHER.matches(request);
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {
        String token = bearerToken(request);
        if (!StringUtils.hasText(token)) {
            filterChain.doFilter(request, response);
            return;
        }

        try {
            Claims claims = Jwts.parser()
                    .verifyWith(signingKey())
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();

            validateClaims(claims);

            List<SimpleGrantedAuthority> authorities = List.of(
                    new SimpleGrantedAuthority("SERVICE_TERRA_CORTEX"),
                    new SimpleGrantedAuthority("SCOPE_" + REQUIRED_SCOPE)
            );
            UsernamePasswordAuthenticationToken authentication =
                    new UsernamePasswordAuthenticationToken(
                            "service:" + claims.getSubject(),
                            null,
                            authorities
                    );
            SecurityContextHolder.getContext().setAuthentication(authentication);
            log.debug("Authenticated internal service subject={}", claims.getSubject());
        } catch (Exception ex) {
            log.warn("Rejected internal service token: {}", ex.getMessage());
        }

        filterChain.doFilter(request, response);
    }

    private void validateClaims(Claims claims) {
        if (!expectedIssuer.equals(claims.getIssuer())) {
            throw new IllegalArgumentException("unexpected service token issuer");
        }
        if (!allowedSubject.equals(claims.getSubject())) {
            throw new IllegalArgumentException("unexpected service token subject");
        }
        if (!"service".equals(claims.get("type", String.class))) {
            throw new IllegalArgumentException("service token type is required");
        }
        if (!audienceContains(claims.get("aud"))) {
            throw new IllegalArgumentException("unexpected service token audience");
        }
        if (!scopeContains(claims.get("scope"))) {
            throw new IllegalArgumentException("required service token scope is missing");
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
            return List.of(scopes.split("\\s+" )).contains(REQUIRED_SCOPE);
        }
        if (scopeClaim instanceof Collection<?> scopes) {
            return scopes.stream().anyMatch(REQUIRED_SCOPE::equals);
        }
        return false;
    }

    private SecretKey signingKey() {
        return Keys.hmacShaKeyFor(serviceJwtSecret.getBytes(StandardCharsets.UTF_8));
    }

    private String bearerToken(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (StringUtils.hasText(header) && header.startsWith("Bearer ")) {
            return header.substring(7);
        }
        return null;
    }
}
