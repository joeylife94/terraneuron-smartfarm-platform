package com.terraneuron.ops.service.safety;

import com.terraneuron.ops.entity.ActionPlan;
import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;

class SafetyValidatorTest {

    private ActionPlan.ActionPlanBuilder validPlanBuilder() {
        return ActionPlan.builder()
                .planId("plan-1")
                .traceId("trace-0000000000000001")
                .farmId("farm-1")
                .targetAssetId("fan-01")
                .targetAssetType("device")
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
        SafetyValidator validator = new SafetyValidator(plan -> DeviceSafetyClient.DeviceSafetyResult.allowed());
        ActionPlan plan = validPlanBuilder().status(ActionPlan.PlanStatus.PENDING).build();

        SafetyValidator.ValidationResult result = validator.validate(plan);

        assertThat(result.isOverallPassed()).isFalse();
        assertThat(result.getFailedLayer()).isEqualTo("PERMISSION");
        assertThat(result.getFailureReasonCode()).isEqualTo("HUMAN_APPROVAL_REQUIRED");
    }

    @Test
    void approvedPlanWithFreshDevicePassesAllLayers() {
        SafetyValidator validator = new SafetyValidator(plan -> DeviceSafetyClient.DeviceSafetyResult.allowed());
        ActionPlan plan = approvedPlan();

        SafetyValidator.ValidationResult result = validator.validate(plan);

        assertThat(result.isOverallPassed()).isTrue();
        assertThat(result.getRecommendedAction()).isEqualTo("EXECUTE");
    }

    @Test
    void approvedPlanWithoutApproverMetadataFailsPermissionLayer() {
        SafetyValidator validator = new SafetyValidator(plan -> DeviceSafetyClient.DeviceSafetyResult.allowed());
        ActionPlan plan = validPlanBuilder().status(ActionPlan.PlanStatus.APPROVED).build();

        SafetyValidator.ValidationResult result = validator.validate(plan);

        assertThat(result.getFailedLayer()).isEqualTo("PERMISSION");
        assertThat(result.getPermissionValidation().getErrors())
                .contains("APPROVER_REQUIRED", "APPROVAL_TIME_REQUIRED");
    }

    @Test
    void missingRequiredFieldsFailLogicalLayer() {
        SafetyValidator validator = new SafetyValidator(plan -> DeviceSafetyClient.DeviceSafetyResult.allowed());
        ActionPlan plan = approvedPlan();
        plan.setTargetAssetId(null);
        plan.setActionType(null);

        SafetyValidator.ValidationResult result = validator.validate(plan);

        assertThat(result.getFailedLayer()).isEqualTo("LOGICAL");
        assertThat(result.getLogicalValidation().getErrors())
                .contains("ASSET_ID_REQUIRED", "ACTION_TYPE_REQUIRED");
    }

    @Test
    void deviceBlockUsesStableLayerAndReasonCode() {
        SafetyValidator validator = new SafetyValidator(
                plan -> DeviceSafetyClient.DeviceSafetyResult.blocked("STATE_STALE"));

        SafetyValidator.ValidationResult result = validator.validate(approvedPlan());

        assertThat(result.isOverallPassed()).isFalse();
        assertThat(result.getFailedLayer()).isEqualTo("DEVICE_STATE");
        assertThat(result.getFailureReasonCode()).isEqualTo("STATE_STALE");
        assertThat(result.getAllErrors()).containsExactly("DEVICE_SAFETY_BLOCKED:STATE_STALE");
    }

    private ActionPlan approvedPlan() {
        return validPlanBuilder()
                .status(ActionPlan.PlanStatus.APPROVED)
                .approvedBy("operator")
                .approvedAt(Instant.now())
                .build();
    }
}
