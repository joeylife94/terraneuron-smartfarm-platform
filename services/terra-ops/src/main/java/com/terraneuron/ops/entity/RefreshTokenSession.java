package com.terraneuron.ops.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;

import java.time.Instant;

/**
 * Server-side refresh-token session.
 *
 * The raw JWT is never persisted. {@code tokenHash} contains a SHA-256 digest
 * used to bind a signed token to the exact server-side session row.
 */
@Entity
@Table(name = "refresh_token_sessions", indexes = {
        @Index(name = "uk_refresh_token_id", columnList = "token_id", unique = true),
        @Index(name = "uk_refresh_token_hash", columnList = "token_hash", unique = true),
        @Index(name = "idx_refresh_username", columnList = "username"),
        @Index(name = "idx_refresh_family", columnList = "family_id"),
        @Index(name = "idx_refresh_expires_at", columnList = "expires_at")
})
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@ToString(exclude = "tokenHash")
public class RefreshTokenSession {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "token_id", nullable = false, unique = true, length = 36)
    private String tokenId;

    @Column(name = "token_hash", nullable = false, unique = true, length = 64)
    private String tokenHash;

    @Column(nullable = false, length = 50)
    private String username;

    @Column(name = "family_id", nullable = false, length = 36)
    private String familyId;

    @Column(name = "issued_at", nullable = false)
    private Instant issuedAt;

    @Column(name = "expires_at", nullable = false)
    private Instant expiresAt;

    @Column(name = "revoked_at")
    private Instant revokedAt;

    @Column(name = "revoke_reason", length = 50)
    private String revokeReason;

    @Column(name = "replaced_by_token_id", length = 36)
    private String replacedByTokenId;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    void onCreate() {
        Instant now = Instant.now();
        if (createdAt == null) {
            createdAt = now;
        }
        updatedAt = now;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = Instant.now();
    }

    public boolean isActiveAt(Instant now) {
        return revokedAt == null && expiresAt.isAfter(now);
    }

    public void revoke(Instant when, String reason, String replacementTokenId) {
        if (revokedAt == null) {
            revokedAt = when;
            revokeReason = reason;
            replacedByTokenId = replacementTokenId;
        }
    }
}
