package com.terraneuron.ops.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;

/** Records lifecycle events for compliance and traceability. */
@Entity
@Table(name = "audit_logs", indexes = {
    @Index(name = "idx_audit_trace_id", columnList = "trace_id"),
    @Index(name = "idx_audit_entity", columnList = "entity_type, entity_id"),
    @Index(name = "idx_audit_event_type", columnList = "event_type"),
    @Index(name = "idx_audit_timestamp", columnList = "timestamp"),
    @Index(name = "idx_audit_actor", columnList = "actor")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AuditLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "log_id", nullable = false, unique = true, length = 50)
    private String logId;

    @Column(name = "trace_id", nullable = false, length = 100)
    private String traceId;

    @Column(name = "log_type", length = 30)
    @Builder.Default
    private String logType = "activity";

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(name = "event_type", nullable = false, length = 30)
    private EventType eventType;

    @Column(name = "entity_type", nullable = false, length = 30)
    private String entityType;

    @Column(name = "entity_id", nullable = false, length = 50)
    private String entityId;

    @Column(name = "actor", nullable = false, length = 100)
    private String actor;

    @Column(name = "action", nullable = false, length = 255)
    private String action;

    @Column(name = "details", columnDefinition = "JSON")
    private String details;

    @Column(name = "timestamp", nullable = false)
    private Instant timestamp;

    @Column(name = "success", nullable = false)
    @Builder.Default
    private Boolean success = true;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "ip_address", length = 45)
    private String ipAddress;

    @Column(name = "user_agent", length = 255)
    private String userAgent;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
        if (timestamp == null) timestamp = Instant.now();
        if (logId == null) {
            logId = "log-" + java.util.UUID.randomUUID().toString().substring(0, 8);
        }
    }

    public enum EventType {
        PLAN_CREATED,
        PLAN_VALIDATED,
        PLAN_APPROVED,
        PLAN_SAFETY_BLOCKED,
        PLAN_SAFETY_CLEARED,
        PLAN_REJECTED,
        PLAN_EXPIRED,
        PLAN_CANCELLED,
        COMMAND_QUEUED,
        COMMAND_EXECUTED,
        COMMAND_FAILED,
        COMMAND_TIMEOUT,
        ALERT_TRIGGERED,
        ALERT_ACKNOWLEDGED,
        ALERT_RESOLVED,
        ALERT_ESCALATED,
        INSIGHT_DETECTED,
        INSIGHT_PROCESSED,
        SYSTEM_ERROR,
        SECURITY_VIOLATION,
        CONFIG_CHANGED
    }
}
