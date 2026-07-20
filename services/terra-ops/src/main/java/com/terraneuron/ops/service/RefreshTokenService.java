package com.terraneuron.ops.service;

import com.terraneuron.ops.entity.RefreshTokenSession;
import com.terraneuron.ops.repository.RefreshTokenSessionRepository;
import com.terraneuron.ops.security.JwtTokenProvider;
import com.terraneuron.ops.security.JwtTokenProvider.GeneratedRefreshToken;
import com.terraneuron.ops.security.JwtTokenProvider.RefreshTokenClaims;
import com.terraneuron.ops.service.UserAuthenticationService.AuthenticatedUser;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Optional;

/**
 * Persists, rotates and revokes refresh-token sessions.
 *
 * Rotation is serialized with a pessimistic row lock. Reuse of a token that was
 * already rotated revokes every still-active token in the same family.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RefreshTokenService {

    static final String REASON_ROTATED = "ROTATED";
    static final String REASON_LOGOUT = "LOGOUT";
    static final String REASON_REUSE_DETECTED = "REUSE_DETECTED";
    static final String REASON_ACCOUNT_UNAVAILABLE = "ACCOUNT_UNAVAILABLE";
    static final String REASON_INTEGRITY_FAILURE = "INTEGRITY_FAILURE";
    static final String REASON_EXPIRED = "EXPIRED";

    private final JwtTokenProvider tokenProvider;
    private final RefreshTokenSessionRepository sessionRepository;
    private final UserAuthenticationService authenticationService;

    /** Creates and persists the first refresh token in a new token family. */
    @Transactional
    public IssuedRefreshToken issue(String username) {
        GeneratedRefreshToken generated = tokenProvider.generateRefreshTokenSession(username);
        sessionRepository.save(toSession(username, generated));
        return new IssuedRefreshToken(generated.token(), generated.expiresAt());
    }

    /**
     * Atomically consumes one active refresh token and replaces it with a new
     * token in the same family.
     */
    @Transactional
    public Optional<RotationResult> rotate(String rawToken) {
        Optional<RefreshTokenClaims> parsed = tokenProvider.parseRefreshTokenForRotation(rawToken);
        if (parsed.isEmpty()) {
            return Optional.empty();
        }

        RefreshTokenClaims claims = parsed.get();
        Optional<RefreshTokenSession> locked = sessionRepository.findByTokenIdForUpdate(claims.tokenId());
        if (locked.isEmpty()) {
            return Optional.empty();
        }

        RefreshTokenSession current = locked.get();
        Instant now = Instant.now();

        if (!matchesPersistedSession(current, claims, rawToken)) {
            revokeFamily(current.getFamilyId(), now, REASON_INTEGRITY_FAILURE);
            return Optional.empty();
        }

        // Reuse detection precedes expiry handling. A known token that was
        // rotated remains replay evidence even after its own JWT expiry.
        if (current.getRevokedAt() != null) {
            if (REASON_ROTATED.equals(current.getRevokeReason())) {
                revokeFamily(current.getFamilyId(), now, REASON_REUSE_DETECTED);
                log.warn("Refresh-token reuse detected; active token family revoked");
            }
            return Optional.empty();
        }

        if (!current.isActiveAt(now) || !claims.expiresAt().isAfter(now)) {
            current.revoke(now, REASON_EXPIRED, null);
            sessionRepository.save(current);
            return Optional.empty();
        }

        Optional<AuthenticatedUser> account = authenticationService.findEnabledByUsername(claims.username());
        if (account.isEmpty()) {
            revokeFamily(current.getFamilyId(), now, REASON_ACCOUNT_UNAVAILABLE);
            return Optional.empty();
        }

        GeneratedRefreshToken replacement = tokenProvider.generateRefreshTokenSession(
                claims.username(),
                current.getFamilyId());

        current.revoke(now, REASON_ROTATED, replacement.tokenId());
        sessionRepository.save(current);
        sessionRepository.save(toSession(claims.username(), replacement));

        return Optional.of(new RotationResult(
                account.get(),
                replacement.token(),
                replacement.expiresAt()));
    }

    /**
     * Revokes exactly the refresh token presented by the caller. The method is
     * intentionally idempotent and does not disclose whether the token existed.
     */
    @Transactional
    public void revoke(String rawToken) {
        Optional<RefreshTokenClaims> parsed = tokenProvider.parseRefreshToken(rawToken);
        if (parsed.isEmpty()) {
            return;
        }

        RefreshTokenClaims claims = parsed.get();
        sessionRepository.findByTokenIdForUpdate(claims.tokenId())
                .filter(session -> matchesPersistedSession(session, claims, rawToken))
                .filter(session -> session.getRevokedAt() == null)
                .ifPresent(session -> {
                    session.revoke(Instant.now(), REASON_LOGOUT, null);
                    sessionRepository.save(session);
                });
    }

    private void revokeFamily(String familyId, Instant when, String reason) {
        sessionRepository.revokeActiveFamily(familyId, when, reason);
    }

    private boolean matchesPersistedSession(
            RefreshTokenSession session,
            RefreshTokenClaims claims,
            String rawToken) {
        return session.getTokenId().equals(claims.tokenId())
                && session.getFamilyId().equals(claims.familyId())
                && session.getUsername().equals(claims.username())
                && MessageDigest.isEqual(
                        session.getTokenHash().getBytes(StandardCharsets.US_ASCII),
                        hash(rawToken).getBytes(StandardCharsets.US_ASCII));
    }

    private RefreshTokenSession toSession(String username, GeneratedRefreshToken generated) {
        return RefreshTokenSession.builder()
                .tokenId(generated.tokenId())
                .tokenHash(hash(generated.token()))
                .username(username)
                .familyId(generated.familyId())
                .issuedAt(generated.issuedAt())
                .expiresAt(generated.expiresAt())
                .build();
    }

    static String hash(String token) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(token.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }

    public record IssuedRefreshToken(String token, Instant expiresAt) {
    }

    public record RotationResult(
            AuthenticatedUser user,
            String refreshToken,
            Instant refreshExpiresAt) {
    }
}
