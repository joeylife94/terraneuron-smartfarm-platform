package com.terraneuron.ops.service.safety;

import com.terraneuron.ops.entity.ActionPlan;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Four-layer fail-closed validation performed before an outbox event is created. */
@Slf4j
@Component
@RequiredArgsConstructor
public class SafetyValidator {

    private final DeviceSafetyClient deviceSafetyClient;

    public ValidationResult validate(ActionPlan plan) {
        ValidationResult result = ValidationResult.builder()
                .planId(plan.getPlanId())
                .traceId(plan.getTraceId())
                .build();

        LayerResult logical = validateLogical(plan);
        result.setLogicalValidation(logical);
        if (!logical.isPassed()) {
            return fail(result, "LOGICAL", logical);
        }

        LayerResult context = validateContext(plan);
        result.setContextValidation(context);
        if (!context.isPassed()) {
            return fail(result, "CONTEXT", context);
        }

        LayerResult permission = validatePermission(plan);
        result.setPermissionValidation(permission);
        if (!permission.isPassed()) {
            return fail(result, "PERMISSION", permission);
        }

        LayerResult device = validateDeviceState(plan);
        result.setDeviceStateValidation(device);
        if (!device.isPassed()) {
            return fail(result, "DEVICE_STATE", device);
        }

        result.setOverallPassed(true);
        result.setRecommendedAction("EXECUTE");
        result.setFailureReasonCode(null);
        return result;
    }

    private ValidationResult fail(ValidationResult result, String layer, LayerResult layerResult) {
        result.setOverallPassed(false);
        result.setFailedLayer(layer);
        result.setFailureReasonCode(layerResult.getReasonCode());
        result.setRecommendedAction("ALERT_ONLY");
        log.warn("Safety validation blocked: layer={} reason={}", layer, layerResult.getReasonCode());
        return result;
    }

    private LayerResult validateLogical(ActionPlan plan) {
        List<String> errors = new ArrayList<>();
        if (isBlank(plan.getPlanId())) errors.add("PLAN_ID_REQUIRED");
        if (isBlank(plan.getTraceId())) errors.add("TRACE_ID_REQUIRED");
        if (isBlank(plan.getFarmId())) errors.add("FARM_ID_REQUIRED");
        if (isBlank(plan.getTargetAssetId())) errors.add("ASSET_ID_REQUIRED");
        if (isBlank(plan.getActionCategory())) errors.add("ACTION_CATEGORY_REQUIRED");
        if (isBlank(plan.getActionType())) errors.add("ACTION_TYPE_REQUIRED");
        if (plan.isExpired()) errors.add("PLAN_EXPIRED");
        if (plan.getStatus() != ActionPlan.PlanStatus.PENDING
                && plan.getStatus() != ActionPlan.PlanStatus.APPROVED
                && plan.getStatus() != ActionPlan.PlanStatus.SAFETY_BLOCKED) {
            errors.add("PLAN_STATUS_INVALID");
        }
        return layer("LOGICAL", errors, errors.isEmpty() ? "ALLOWED" : errors.get(0));
    }

    private LayerResult validateContext(ActionPlan plan) {
        List<String> warnings = new ArrayList<>();
        if (plan.getPriority() == ActionPlan.ActionPriority.CRITICAL
                && "alert_only".equals(plan.getActionType())) {
            warnings.add("CRITICAL_ALERT_ONLY");
        }
        LayerResult result = layer("CONTEXT", List.of(), "ALLOWED");
        result.setWarnings(warnings);
        return result;
    }

    private LayerResult validatePermission(ActionPlan plan) {
        List<String> errors = new ArrayList<>();
        if (Boolean.TRUE.equals(plan.getRequiresApproval())
                && plan.getStatus() == ActionPlan.PlanStatus.PENDING) {
            errors.add("HUMAN_APPROVAL_REQUIRED");
        }
        if (plan.getStatus() == ActionPlan.PlanStatus.APPROVED
                || plan.getStatus() == ActionPlan.PlanStatus.SAFETY_BLOCKED) {
            if (isBlank(plan.getApprovedBy())) errors.add("APPROVER_REQUIRED");
            if (plan.getApprovedAt() == null) errors.add("APPROVAL_TIME_REQUIRED");
        }
        return layer("PERMISSION", errors, errors.isEmpty() ? "ALLOWED" : errors.get(0));
    }

    private LayerResult validateDeviceState(ActionPlan plan) {
        if (isAlertOnly(plan)) {
            return layer("DEVICE_STATE", List.of(), "NOT_APPLICABLE");
        }

        DeviceSafetyClient.DeviceSafetyResult decision = deviceSafetyClient.evaluate(plan);
        if (decision.allowed()) {
            return layer("DEVICE_STATE", List.of(), "ALLOWED");
        }
        return layer(
                "DEVICE_STATE",
                List.of("DEVICE_SAFETY_BLOCKED:" + decision.reasonCode()),
                decision.reasonCode());
    }

    private LayerResult layer(String name, List<String> errors, String reasonCode) {
        return LayerResult.builder()
                .layerName(name)
                .passed(errors.isEmpty())
                .errors(new ArrayList<>(errors))
                .warnings(new ArrayList<>())
                .reasonCode(reasonCode)
                .build();
    }

    private boolean isAlertOnly(ActionPlan plan) {
        return "alert".equals(normalize(plan.getActionCategory()))
                && "alert_only".equals(normalize(plan.getActionType()));
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ValidationResult {
        private String planId;
        private String traceId;
        private boolean overallPassed;
        private String failedLayer;
        private String failureReasonCode;
        private String recommendedAction;
        private LayerResult logicalValidation;
        private LayerResult contextValidation;
        private LayerResult permissionValidation;
        private LayerResult deviceStateValidation;

        public List<String> getAllErrors() {
            List<String> errors = new ArrayList<>();
            addErrors(errors, logicalValidation);
            addErrors(errors, contextValidation);
            addErrors(errors, permissionValidation);
            addErrors(errors, deviceStateValidation);
            return errors;
        }

        public List<String> getAllWarnings() {
            List<String> warnings = new ArrayList<>();
            addWarnings(warnings, logicalValidation);
            addWarnings(warnings, contextValidation);
            addWarnings(warnings, permissionValidation);
            addWarnings(warnings, deviceStateValidation);
            return warnings;
        }

        private void addErrors(List<String> target, LayerResult layer) {
            if (layer != null && layer.getErrors() != null) target.addAll(layer.getErrors());
        }

        private void addWarnings(List<String> target, LayerResult layer) {
            if (layer != null && layer.getWarnings() != null) target.addAll(layer.getWarnings());
        }
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class LayerResult {
        private String layerName;
        private boolean passed;
        private String reasonCode;
        @Builder.Default
        private List<String> errors = new ArrayList<>();
        @Builder.Default
        private List<String> warnings = new ArrayList<>();
    }
}
