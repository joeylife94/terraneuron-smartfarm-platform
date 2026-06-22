package com.terraneuron.ops.service.safety;

import com.terraneuron.ops.entity.ActionPlan;
import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Focused unit tests for the 4-layer {@link SafetyValidator}.
 *
 * These tests pin down the permission-layer (layer 3) semantics that drive the
 * human-in-the-loop approval flow:
 * <ul>
 *   <li>A PENDING plan that still requires approval must fail (no execution before approval).</li>
 *   <li>An APPROVED plan with approver metadata must pass.</li>
 *   <li>Plans missing required data must fail at the logical layer.</li>
 * </ul>
 */
class SafetyValidatorTest {

    private final SafetyValidator validator = new SafetyValidator();

    private ActionPlan.ActionPlanBuilder validPlanBuilder() {
        return ActionPlan.builder()
                .planId("plan-1")
                .traceId("trace-0000000000000001")
                .farmId("farm-1")
                .targetAssetId("fan-01")
                .actionCategory("ventilation")
                .actionType("turn_on")
                .reasoning("Temperature exceeds threshold")
                .priority(ActionPlan.ActionPriority.MEDIUM)
                .requiresApproval(true)
                .generatedAt(Instant.now())
                .expiresAt(Instant.now().plusSeconds(3600));
    }

    @Test
    void pendingPlanRequiringApprovalFailsPermissionLayer() {
        ActionPlan plan = validPlanBuilder()
                .status(ActionPlan.PlanStatus.PENDING)
                .build();

        SafetyValidator.ValidationResult result = validator.validate(plan);

        assertThat(result.isOverallPassed()).isFalse();
        assertThat(result.getFailedLayer()).isEqualTo("PERMISSION");
        assertThat(result.getPermissionValidation().getErrors())
                .anyMatch(e -> e.contains("requires human approval"));
        assertThat(result.getRecommendedAction()).isEqualTo("ALERT_ONLY");
    }

    @Test
    void approvedPlanWithApproverMetadataPassesAllLayers() {
        ActionPlan plan = validPlanBuilder()
                .status(ActionPlan.PlanStatus.APPROVED)
                .approvedBy("operator")
                .approvedAt(Instant.now())
                .build();

        SafetyValidator.ValidationResult result = validator.validate(plan);

        assertThat(result.isOverallPassed()).isTrue();
        assertThat(result.getFailedLayer()).isNull();
        assertThat(result.getRecommendedAction()).isEqualTo("EXECUTE");
    }

    @Test
    void approvedPlanWithoutApproverMetadataFailsPermissionLayer() {
        ActionPlan plan = validPlanBuilder()
                .status(ActionPlan.PlanStatus.APPROVED)
                // approvedBy / approvedAt deliberately omitted
                .build();

        SafetyValidator.ValidationResult result = validator.validate(plan);

        assertThat(result.isOverallPassed()).isFalse();
        assertThat(result.getFailedLayer()).isEqualTo("PERMISSION");
        assertThat(result.getPermissionValidation().getErrors())
                .anyMatch(e -> e.contains("approver information"));
    }

    @Test
    void planMissingRequiredFieldsFailsLogicalLayer() {
        ActionPlan plan = validPlanBuilder()
                .status(ActionPlan.PlanStatus.APPROVED)
                .approvedBy("operator")
                .approvedAt(Instant.now())
                .targetAssetId(null)   // required field missing
                .actionType(null)      // required field missing
                .build();

        SafetyValidator.ValidationResult result = validator.validate(plan);

        assertThat(result.isOverallPassed()).isFalse();
        assertThat(result.getFailedLayer()).isEqualTo("LOGICAL");
        assertThat(result.getLogicalValidation().getErrors())
                .anyMatch(e -> e.contains("target_asset_id"))
                .anyMatch(e -> e.contains("action_type"));
    }

    @Test
    void expiredPlanFailsLogicalLayer() {
        ActionPlan plan = validPlanBuilder()
                .status(ActionPlan.PlanStatus.APPROVED)
                .approvedBy("operator")
                .approvedAt(Instant.now())
                .expiresAt(Instant.now().minusSeconds(60))
                .build();

        SafetyValidator.ValidationResult result = validator.validate(plan);

        assertThat(result.isOverallPassed()).isFalse();
        assertThat(result.getFailedLayer()).isEqualTo("LOGICAL");
        assertThat(result.getLogicalValidation().getErrors())
                .anyMatch(e -> e.contains("expired"));
    }
}
