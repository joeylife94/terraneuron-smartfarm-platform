package com.terraneuron.ops.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;

/** JWT token provider for interactive Terra-Ops users. */
@Slf4j
@Component
public class JwtTokenProvider {

    private static final String ACCESS_TYPE = "access";
    private static final String REFRESH_TYPE = "refresh";
    private static final String REFRESH_FAMILY_CLAIM = "family";

    @Value("${jwt.secret}")
    private String jwtSecret;

    @Value("${jwt.expiration:86400000}") // 24 hours default
    private long jwtExpiration;

    @Value("${jwt.refresh-expiration:604800000}") // 7 days default
    private long refreshExpiration;

    @PostConstruct
    void validateJwtSecret() {
        if (!StringUtils.hasText(jwtSecret)) {
            throw new IllegalStateException("JWT_SECRET is required and must not be blank.");
        }
        if (jwtSecret.getBytes(StandardCharsets.UTF_8).length < 32) {
            throw new IllegalStateException("JWT_SECRET must be at least 32 bytes for HMAC-SHA signing.");
        }
    }

    private SecretKey getSigningKey() {
        byte[] keyBytes = jwtSecret.getBytes(StandardCharsets.UTF_8);
        return Keys.hmacShaKeyFor(keyBytes);
    }

    /** Generate an access token from a Spring Security authentication. */
    public String generateToken(Authentication authentication) {
        String username = authentication.getName();
        String authorities = authentication.getAuthorities().stream()
                .map(GrantedAuthority::getAuthority)
                .collect(Collectors.joining(","));
        return generateToken(username, authorities);
    }

    /** Generate an access token for a specific user and current role claim. */
    public String generateToken(String username, String roles) {
        Date now = new Date();
        Date expiryDate = new Date(now.getTime() + jwtExpiration);

        return Jwts.builder()
                .subject(username)
                .claim("roles", roles)
                .claim("type", ACCESS_TYPE)
                .issuedAt(now)
                .expiration(expiryDate)
                .signWith(getSigningKey())
                .compact();
    }

    /**
     * Compatibility helper. Runtime authentication flows should persist the
     * metadata returned by {@link #generateRefreshTokenSession(String)}.
     */
    public String generateRefreshToken(String username) {
        return generateRefreshTokenSession(username).token();
    }

    /** Generate the first refresh token in a new rotation family. */
    public GeneratedRefreshToken generateRefreshTokenSession(String username) {
        return generateRefreshTokenSession(username, UUID.randomUUID().toString());
    }

    /** Generate a replacement refresh token in an existing rotation family. */
    public GeneratedRefreshToken generateRefreshTokenSession(String username, String familyId) {
        if (!StringUtils.hasText(username) || !StringUtils.hasText(familyId)) {
            throw new IllegalArgumentException("username and familyId are required");
        }

        String tokenId = UUID.randomUUID().toString();
        Instant issuedAt = Instant.now();
        Instant expiresAt = issuedAt.plusMillis(refreshExpiration);

        String token = Jwts.builder()
                .id(tokenId)
                .subject(username)
                .claim("type", REFRESH_TYPE)
                .claim(REFRESH_FAMILY_CLAIM, familyId)
                .issuedAt(Date.from(issuedAt))
                .expiration(Date.from(expiresAt))
                .signWith(getSigningKey())
                .compact();

        return new GeneratedRefreshToken(token, tokenId, familyId, issuedAt, expiresAt);
    }

    /** Parse a non-expired refresh token with every required rotation claim. */
    public Optional<RefreshTokenClaims> parseRefreshToken(String token) {
        if (!StringUtils.hasText(token)) {
            return Optional.empty();
        }

        try {
            return toRefreshTokenClaims(parseClaims(token));
        } catch (JwtException | IllegalArgumentException exception) {
            log.debug("Refresh JWT validation failed: {}", exception.getMessage());
            return Optional.empty();
        }
    }

    /**
     * Parse refresh identity for rotation and replay handling.
     *
     * An expired token cannot authorize a refresh, but its signature-verified
     * identity is still needed to load the persisted row and detect reuse of a
     * token that was previously rotated. Expired claims are accepted only by
     * this rotation-specific method; normal token validation remains strict.
     */
    public Optional<RefreshTokenClaims> parseRefreshTokenForRotation(String token) {
        if (!StringUtils.hasText(token)) {
            return Optional.empty();
        }

        try {
            return toRefreshTokenClaims(parseClaims(token));
        } catch (ExpiredJwtException exception) {
            return toRefreshTokenClaims(exception.getClaims());
        } catch (JwtException | IllegalArgumentException exception) {
            log.debug("Refresh JWT rotation parsing failed: {}", exception.getMessage());
            return Optional.empty();
        }
    }

    private Optional<RefreshTokenClaims> toRefreshTokenClaims(Claims claims) {
        String type = claims.get("type", String.class);
        String username = claims.getSubject();
        String tokenId = claims.getId();
        String familyId = claims.get(REFRESH_FAMILY_CLAIM, String.class);
        Date issuedAt = claims.getIssuedAt();
        Date expiresAt = claims.getExpiration();

        if (!REFRESH_TYPE.equals(type)
                || !StringUtils.hasText(username)
                || !StringUtils.hasText(tokenId)
                || !StringUtils.hasText(familyId)
                || issuedAt == null
                || expiresAt == null) {
            return Optional.empty();
        }

        return Optional.of(new RefreshTokenClaims(
                username,
                tokenId,
                familyId,
                issuedAt.toInstant(),
                expiresAt.toInstant()));
    }

    /** Extract username from any valid signed token. */
    public String getUsernameFromToken(String token) {
        return parseClaims(token).getSubject();
    }

    /** Extract roles from an access token. */
    public String getRolesFromToken(String token) {
        return parseClaims(token).get("roles", String.class);
    }

    /** Validate a signed token without requiring a token type. */
    public boolean validateToken(String token) {
        return validateTokenType(token, null);
    }

    /** Validate a signed access token. */
    public boolean validateAccessToken(String token) {
        return validateTokenType(token, ACCESS_TYPE);
    }

    /** Validate a non-expired signed refresh token with all rotation claims present. */
    public boolean validateRefreshToken(String token) {
        return parseRefreshToken(token).isPresent();
    }

    private boolean validateTokenType(String token, String requiredType) {
        try {
            Claims claims = parseClaims(token);
            return requiredType == null || requiredType.equals(claims.get("type", String.class));
        } catch (JwtException | IllegalArgumentException exception) {
            log.debug("JWT validation failed: {}", exception.getMessage());
            return false;
        }
    }

    private Claims parseClaims(String token) {
        return Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    public long getAccessTokenExpirationSeconds() {
        return jwtExpiration / 1000;
    }

    public long getRefreshTokenExpirationSeconds() {
        return refreshExpiration / 1000;
    }

    public boolean isTokenExpired(String token) {
        try {
            return parseClaims(token).getExpiration().before(new Date());
        } catch (Exception exception) {
            return true;
        }
    }

    public record GeneratedRefreshToken(
            String token,
            String tokenId,
            String familyId,
            Instant issuedAt,
            Instant expiresAt) {
    }

    public record RefreshTokenClaims(
            String username,
            String tokenId,
            String familyId,
            Instant issuedAt,
            Instant expiresAt) {
    }
}
