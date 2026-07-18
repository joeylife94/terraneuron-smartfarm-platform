package com.terraneuron.ops.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;

/**
 * Transactional outbox record for a device command.
 *
 * The ActionPlan transition to DISPATCHING and this record are committed in the
 * same MySQL transaction. Kafka publication is performed asynchronously with
 * at-least-once delivery semantics.
 */
@Entity
@Table(
        name = "command_outbox",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_outbox_plan_id",
                columnNames = "plan_id"),
        indexes = {
                @Index(name = "idx_outbox_status_due", columnList = "status,next_attempt_at"),
                @Index(name = "idx_outbox_plan_id", columnList = "plan_id"),
                @Index(name = "idx_outbox_locked_at", columnList = "locked_at")
        })
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CommandOutboxEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "event_id", nullable = false, unique = true, length = 36)
    private String eventId;

    @Column(name = "plan_id", nullable = false, length = 50)
    private String planId;

    @Column(name = "command_id", nullable = false, unique = true, length = 50)
    private String commandId;

    @Column(name = "topic", nullable = false, length = 100)
    private String topic;

    @Column(name = "message_key", nullable = false, length = 100)
    private String messageKey;

    @Column(name = "payload", nullable = false, columnDefinition = "LONGTEXT")
    private String payload;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(name = "status", nullable = false, length = 20)
    @Builder.Default
    private OutboxStatus status = OutboxStatus.PENDING;

    @Column(name = "attempts", nullable = false)
    @Builder.Default
    private int attempts = 0;

    @Column(name = "next_attempt_at", nullable = false)
    private Instant nextAttemptAt;

    @Column(name = "locked_at")
    private Instant lockedAt;

    @Column(name = "published_at")
    private Instant publishedAt;

    @Column(name = "last_error", columnDefinition = "TEXT")
    private String lastError;

    @Version
    @Column(name = "version", nullable = false)
    private Long version;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    protected void onCreate() {
        Instant now = Instant.now();
        createdAt = now;
        updatedAt = now;
        if (nextAttemptAt == null) {
            nextAttemptAt = now;
        }
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = Instant.now();
    }

    public enum OutboxStatus {
        PENDING,
        PROCESSING,
        PUBLISHED,
        DEAD
    }
}
