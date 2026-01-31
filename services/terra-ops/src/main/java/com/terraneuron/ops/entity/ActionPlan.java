package com.terraneuron.ops.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * Action Plan Entity - CloudEvents v1.0 Compliant
 * Represents AI-generated action recommendations awaiting human approval.
 * FarmOS Compatible: Maps to Plan entity structure.
 */
@Entity
@Table(name = "action_plans", indexes = {
    @Index(name = "idx_plan_farm_id", columnList = "farm_id"),
    @Index(name = "idx_plan_status", columnList = "status"),
    @Index(name = "idx_plan_trace_id", columnList = "trace_id"),
    @Index(name = "idx_plan_priority", columnList = "priority"),
    @Index(name = "idx_plan_expires_at", columnList = "expires_at")
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
    private String planType = "input"; // FarmOS: input, harvest, maintenance

    @Column(name = "target_asset_id", nullable = false, length = 50)
    private String targetAssetId;

    @Column(name = "target_asset_type", length = 30)
    @Builder.Default
    private String targetAssetType = "device";

    @Column(name = "action_category", nullable = false, length = 30)
    private String actionCategory; // ventilation, irrigation, lighting, heating, cooling, alert

    @Column(name = "action_type", nullable = false, length = 30)
    private String actionType; // turn_on, turn_off, adjust, alert_only

    @Column(name = "parameters", columnDefinition = "JSON")
    private String parameters; // JSON string of action parameters

    @Column(name = "reasoning", columnDefinition = "TEXT")
    private String reasoning;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    @Builder.Default
    private PlanStatus status = PlanStatus.PENDING;

    @Enumerated(EnumType.STRING)
    @Column(name = "priority", nullable = false, length = 20)
    @Builder.Default
    private ActionPriority priority = ActionPriority.MEDIUM;

    @Column(name = "estimated_impact", columnDefinition = "TEXT")
    private String estimatedImpact;

    @Column(name = "safety_conditions", columnDefinition = "JSON")
    private String safetyConditions; // JSON array of required conditions

    @Column(name = "requires_approval")
    @Builder.Default
    private Boolean requiresApproval = true;

    // Approval tracking
    @Column(name = "approved_by", length = 100)
    private String approvedBy;

    @Column(name = "approved_at")
    private Instant approvedAt;

    @Column(name = "rejection_reason", columnDefinition = "TEXT")
    private String rejectionReason;

    // Execution tracking
    @Column(name = "executed_at")
    private Instant executedAt;

    @Column(name = "execution_result", length = 50)
    private String executionResult;

    @Column(name = "execution_error", columnDefinition = "TEXT")
    private String executionError;

    // Timestamps
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
        if (generatedAt == null) {
            generatedAt = Instant.now();
        }
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = Instant.now();
    }

    /**
     * Check if the plan has expired
     */
    public boolean isExpired() {
        return expiresAt != null && Instant.now().isAfter(expiresAt);
    }

    /**
     * Check if the plan can be approved
     */
    public boolean canBeApproved() {
        return status == PlanStatus.PENDING && !isExpired();
    }

    /**
     * Check if the plan can be executed
     */
    public boolean canBeExecuted() {
        return status == PlanStatus.APPROVED && !isExpired();
    }

    public enum PlanStatus {
        PENDING,      // Awaiting human approval
        APPROVED,     // Approved, ready for execution
        REJECTED,     // Rejected by human
        EXECUTED,     // Successfully executed
        FAILED,       // Execution failed
        EXPIRED,      // Plan expired before action
        CANCELLED     // Cancelled by user
    }

    public enum ActionPriority {
        LOW,
        MEDIUM,
        HIGH,
        CRITICAL
    }
}
