package com.terraneuron.ops.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * Audit Log Entity - FarmOS Compatible
 * Records all lifecycle events for compliance and traceability.
 * Maps to FarmOS Log entity (type: activity).
 */
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
    private String logType = "activity"; // FarmOS standard

    @Enumerated(EnumType.STRING)
    @Column(name = "event_type", nullable = false, length = 30)
    private EventType eventType;

    @Column(name = "entity_type", nullable = false, length = 30)
    private String entityType; // plan, command, alert, insight

    @Column(name = "entity_id", nullable = false, length = 50)
    private String entityId;

    @Column(name = "actor", nullable = false, length = 100)
    private String actor; // user_id or "system"

    @Column(name = "action", nullable = false, length = 100)
    private String action; // Human-readable action description

    @Column(name = "details", columnDefinition = "JSON")
    private String details; // Additional context as JSON

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
        if (timestamp == null) {
            timestamp = Instant.now();
        }
        if (logId == null) {
            logId = "log-" + java.util.UUID.randomUUID().toString().substring(0, 8);
        }
    }

    /**
     * Event types for audit logging
     */
    public enum EventType {
        // Plan lifecycle
        PLAN_CREATED,      // AI generated a new plan
        PLAN_VALIDATED,    // Safety validation completed
        PLAN_APPROVED,     // Human approved the plan
        PLAN_REJECTED,     // Human rejected the plan
        PLAN_EXPIRED,      // Plan expired without action
        PLAN_CANCELLED,    // Plan cancelled by user
        
        // Command lifecycle
        COMMAND_QUEUED,    // Command added to execution queue
        COMMAND_EXECUTED,  // Command successfully executed
        COMMAND_FAILED,    // Command execution failed
        COMMAND_TIMEOUT,   // Command execution timed out
        
        // Alert lifecycle
        ALERT_TRIGGERED,   // New alert generated
        ALERT_ACKNOWLEDGED,// Alert acknowledged by user
        ALERT_RESOLVED,    // Alert condition resolved
        ALERT_ESCALATED,   // Alert escalated to higher priority
        
        // Insight lifecycle
        INSIGHT_DETECTED,  // AI detected an insight
        INSIGHT_PROCESSED, // Insight processed and stored
        
        // System events
        SYSTEM_ERROR,      // System-level error
        SECURITY_VIOLATION,// Security policy violation
        CONFIG_CHANGED     // Configuration change
    }
}
