package com.terraneuron.ops.service.safety;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.util.Date;

/** Mints narrowly scoped Terra-Ops service credentials for Terra-Sense safety evaluation. */
@Component
public class SenseServiceJwtProvider {

    private final Clock clock;

    @Value("${device-safety.client.jwt.secret}")
    private String secret;

    @Value("${device-safety.client.jwt.issuer:terraneuron-internal}")
    private String issuer;

    @Value("${device-safety.client.jwt.subject:terra-ops}")
    private String subject;

    @Value("${device-safety.client.jwt.audience:terra-sense}")
    private String audience;

    @Value("${device-safety.client.jwt.scope:device:safety:evaluate}")
    private String scope;

    @Value("${device-safety.client.jwt.lifetime-seconds:30}")
    private long lifetimeSeconds;

    public SenseServiceJwtProvider(Clock clock) {
        this.clock = clock;
    }

    @PostConstruct
    void validateConfiguration() {
        if (!StringUtils.hasText(secret)
                || secret.getBytes(StandardCharsets.UTF_8).length < 32) {
            throw new IllegalStateException(
                    "DEVICE_SAFETY_JWT_SECRET is required and must be at least 32 bytes");
        }
        if (lifetimeSeconds <= 0 || lifetimeSeconds > 60) {
            throw new IllegalStateException("Device safety service JWT lifetime must be 1-60 seconds");
        }
    }

    public String createToken() {
        Instant issuedAt = clock.instant();
        Instant expiration = issuedAt.plusSeconds(lifetimeSeconds);
        return Jwts.builder()
                .issuer(issuer)
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
        return Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }
}
