package com.terraneuron.ops.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;

/** AI-generated action recommendation with approval, safety, and command lifecycle state. */
@Entity
@Table(name = "action_plans", indexes = {
    @Index(name = "idx_plan_farm_id", columnList = "farm_id"),
    @Index(name = "idx_plan_status", columnList = "status"),
    @Index(name = "idx_plan_trace_id", columnList = "trace_id"),
    @Index(name = "idx_plan_priority", columnList = "priority"),
    @Index(name = "idx_plan_expires_at", columnList = "expires_at"),
    @Index(name = "idx_plan_command_id", columnList = "command_id"),
    @Index(name = "idx_plan_ack_deadline", columnList = "ack_deadline_at")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ActionPlan {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "plan_id", nullable = false, unique = true, length = 50)
    private String planId;

    @Column(name = "trace_id", nullable = false, length = 100)
    private String traceId;

    @Column(name = "farm_id", nullable = false, length = 50)
    private String farmId;

    @Column(name = "plan_type", length = 30)
    @Builder.Default
    private String planType = "input";

    @Column(name = "target_asset_id", nullable = false, length = 50)
    private String targetAssetId;

    @Column(name = "target_asset_type", length = 30)
    @Builder.Default
    private String targetAssetType = "device";

    @Column(name = "action_category", nullable = false, length = 30)
    private String actionCategory;

    @Column(name = "action_type", nullable = false, length = 30)
    private String actionType;

    @Column(name = "parameters", columnDefinition = "JSON")
    private String parameters;

    @Column(name = "reasoning", columnDefinition = "TEXT")
    private String reasoning;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(name = "status", nullable = false, length = 20)
    @Builder.Default
    private PlanStatus status = PlanStatus.PENDING;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(name = "priority", nullable = false, length = 20)
    @Builder.Default
    private ActionPriority priority = ActionPriority.MEDIUM;

    @Column(name = "estimated_impact", columnDefinition = "TEXT")
    private String estimatedImpact;

    @Column(name = "safety_conditions", columnDefinition = "JSON")
    private String safetyConditions;

    @Column(name = "requires_approval")
    @Builder.Default
    private Boolean requiresApproval = true;

    @Column(name = "approved_by", length = 100)
    private String approvedBy;

    @Column(name = "approved_at")
    private Instant approvedAt;

    @Column(name = "rejection_reason", columnDefinition = "TEXT")
    private String rejectionReason;

    @Column(name = "safety_block_reason_code", length = 64)
    private String safetyBlockReasonCode;

    @Column(name = "safety_blocked_at")
    private Instant safetyBlockedAt;

    @Column(name = "command_id", length = 50)
    private String commandId;

    @Column(name = "dispatched_at")
    private Instant dispatchedAt;

    @Column(name = "delivered_at")
    private Instant deliveredAt;

    @Column(name = "ack_deadline_at")
    private Instant ackDeadlineAt;

    @Column(name = "executed_at")
    private Instant executedAt;

    @Column(name = "execution_result", length = 50)
    private String executionResult;

    @Column(name = "execution_error", columnDefinition = "TEXT")
    private String executionError;

    @Column(name = "generated_at", nullable = false)
    private Instant generatedAt;

    @Column(name = "expires_at")
    private Instant expiresAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at")
    private Instant updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
        updatedAt = Instant.now();
        if (generatedAt == null) generatedAt = Instant.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = Instant.now();
    }

    public boolean isExpired() {
        return expiresAt != null && Instant.now().isAfter(expiresAt);
    }

    public boolean canBeApproved() {
        return status == PlanStatus.PENDING && !isExpired();
    }

    public boolean canBeSafetyRevalidated() {
        return status == PlanStatus.SAFETY_BLOCKED
                && commandId == null
                && !isExpired();
    }

    public boolean canBeDispatched() {
        return status == PlanStatus.APPROVED
                && commandId == null
                && !isExpired();
    }

    public enum PlanStatus {
        PENDING,
        APPROVED,
        SAFETY_BLOCKED,
        DISPATCHING,
        DISPATCHED,
        DELIVERED,
        EXECUTED,
        REJECTED,
        DISPATCH_FAILED,
        DELIVERY_FAILED,
        EXECUTION_FAILED,
        ACK_TIMEOUT,
        FAILED,
        EXPIRED,
        CANCELLED
    }

    public enum ActionPriority {
        LOW,
        MEDIUM,
        HIGH,
        CRITICAL
    }
}
