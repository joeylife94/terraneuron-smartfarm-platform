package com.terraneuron.ops.service.safety;

import com.terraneuron.ops.entity.ActionPlan;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * 4-Layer Safety Validation System
 * Ensures all action plans pass strict safety checks before execution.
 * 
 * Layer 1: Logical Validation - Basic data integrity
 * Layer 2: Context Validation - Environmental/situational checks
 * Layer 3: Permission Validation - Authorization checks
 * Layer 4: Device State Validation - Target device readiness
 * 
 * Fail-Safe Design: Default to ALERT_ONLY on any validation failure
 */
@Slf4j
@Component
public class SafetyValidator {

    /**
     * Execute all 4 layers of safety validation
     * @param plan The action plan to validate
     * @return Validation result with detailed layer-by-layer results
     */
    public ValidationResult validate(ActionPlan plan) {
        log.info("🛡️ Starting 4-layer safety validation for plan: {}", plan.getPlanId());
        
        ValidationResult result = ValidationResult.builder()
                .planId(plan.getPlanId())
                .traceId(plan.getTraceId())
                .build();
        
        // Layer 1: Logical Validation
        LayerResult logicalResult = validateLogical(plan);
        result.setLogicalValidation(logicalResult);
        if (!logicalResult.isPassed()) {
            result.setOverallPassed(false);
            result.setFailedLayer("LOGICAL");
            result.setRecommendedAction("ALERT_ONLY");
            log.warn("❌ Layer 1 (Logical) validation failed: {}", logicalResult.getErrors());
            return result;
        }
        log.info("   ✅ Layer 1 (Logical) passed");
        
        // Layer 2: Context Validation
        LayerResult contextResult = validateContext(plan);
        result.setContextValidation(contextResult);
        if (!contextResult.isPassed()) {
            result.setOverallPassed(false);
            result.setFailedLayer("CONTEXT");
            result.setRecommendedAction("ALERT_ONLY");
            log.warn("❌ Layer 2 (Context) validation failed: {}", contextResult.getErrors());
            return result;
        }
        log.info("   ✅ Layer 2 (Context) passed");
        
        // Layer 3: Permission Validation
        LayerResult permissionResult = validatePermission(plan);
        result.setPermissionValidation(permissionResult);
        if (!permissionResult.isPassed()) {
            result.setOverallPassed(false);
            result.setFailedLayer("PERMISSION");
            result.setRecommendedAction("ALERT_ONLY");
            log.warn("❌ Layer 3 (Permission) validation failed: {}", permissionResult.getErrors());
            return result;
        }
        log.info("   ✅ Layer 3 (Permission) passed");
        
        // Layer 4: Device State Validation
        LayerResult deviceResult = validateDeviceState(plan);
        result.setDeviceStateValidation(deviceResult);
        if (!deviceResult.isPassed()) {
            result.setOverallPassed(false);
            result.setFailedLayer("DEVICE_STATE");
            result.setRecommendedAction("ALERT_ONLY");
            log.warn("❌ Layer 4 (DeviceState) validation failed: {}", deviceResult.getErrors());
            return result;
        }
        log.info("   ✅ Layer 4 (DeviceState) passed");
        
        // All layers passed
        result.setOverallPassed(true);
        result.setRecommendedAction("EXECUTE");
        log.info("✅ All 4 safety layers passed for plan: {}", plan.getPlanId());
        
        return result;
    }

    /**
     * Layer 1: Logical Validation
     * Checks basic data integrity and logical consistency
     */
    private LayerResult validateLogical(ActionPlan plan) {
        LayerResult result = LayerResult.builder().layerName("LOGICAL").build();
        List<String> errors = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        
        // Check required fields
        if (plan.getPlanId() == null || plan.getPlanId().isEmpty()) {
            errors.add("plan_id is required");
        }
        if (plan.getTraceId() == null || plan.getTraceId().isEmpty()) {
            errors.add("trace_id is required for distributed tracing");
        }
        if (plan.getFarmId() == null || plan.getFarmId().isEmpty()) {
            errors.add("farm_id is required");
        }
        if (plan.getTargetAssetId() == null || plan.getTargetAssetId().isEmpty()) {
            errors.add("target_asset_id is required");
        }
        if (plan.getActionCategory() == null || plan.getActionCategory().isEmpty()) {
            errors.add("action_category is required");
        }
        if (plan.getActionType() == null || plan.getActionType().isEmpty()) {
            errors.add("action_type is required");
        }
        
        // Check plan expiration
        if (plan.isExpired()) {
            errors.add("Plan has expired at: " + plan.getExpiresAt());
        }
        
        // Check status
        if (plan.getStatus() != ActionPlan.PlanStatus.PENDING && 
            plan.getStatus() != ActionPlan.PlanStatus.APPROVED) {
            errors.add("Plan status must be PENDING or APPROVED, but was: " + plan.getStatus());
        }
        
        // Warnings (non-blocking)
        if (plan.getReasoning() == null || plan.getReasoning().isEmpty()) {
            warnings.add("No reasoning provided for this action plan");
        }
        
        result.setErrors(errors);
        result.setWarnings(warnings);
        result.setPassed(errors.isEmpty());
        
        return result;
    }

    /**
     * Layer 2: Context Validation
     * Checks environmental and situational appropriateness
     */
    private LayerResult validateContext(ActionPlan plan) {
        LayerResult result = LayerResult.builder().layerName("CONTEXT").build();
        List<String> errors = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        
        // Check action category consistency with sensor type
        String actionCategory = plan.getActionCategory();
        String assetId = plan.getTargetAssetId();
        
        // Validate category-asset consistency
        if (actionCategory != null && assetId != null) {
            if (actionCategory.equals("ventilation") && !assetId.contains("fan") && !assetId.contains("vent")) {
                warnings.add("Ventilation action targeting non-ventilation asset: " + assetId);
            }
            if (actionCategory.equals("irrigation") && !assetId.contains("pump") && !assetId.contains("valve") && !assetId.contains("humidifier")) {
                warnings.add("Irrigation action targeting non-irrigation asset: " + assetId);
            }
        }
        
        // Check priority vs action type consistency
        if (plan.getPriority() == ActionPlan.ActionPriority.CRITICAL && 
            "alert_only".equals(plan.getActionType())) {
            warnings.add("CRITICAL priority with alert_only action - consider immediate action");
        }
        
        // TODO: Add real-time context checks (e.g., current weather, time of day, crop growth stage)
        // These would typically query external services or databases
        
        result.setErrors(errors);
        result.setWarnings(warnings);
        result.setPassed(errors.isEmpty());
        
        return result;
    }

    /**
     * Layer 3: Permission Validation
     * Checks authorization and access rights
     */
    private LayerResult validatePermission(ActionPlan plan) {
        LayerResult result = LayerResult.builder().layerName("PERMISSION").build();
        List<String> errors = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        
        // Check if approval is required but not yet given
        if (plan.getRequiresApproval() && plan.getStatus() == ActionPlan.PlanStatus.PENDING) {
            errors.add("Plan requires human approval before execution");
        }
        
        // Check approver information for approved plans
        if (plan.getStatus() == ActionPlan.PlanStatus.APPROVED) {
            if (plan.getApprovedBy() == null || plan.getApprovedBy().isEmpty()) {
                errors.add("Approved plan must have approver information");
            }
            if (plan.getApprovedAt() == null) {
                errors.add("Approved plan must have approval timestamp");
            }
        }
        
        // TODO: Add real permission checks (e.g., user roles, farm ownership, device access)
        // These would typically integrate with the authentication/authorization system
        
        result.setErrors(errors);
        result.setWarnings(warnings);
        result.setPassed(errors.isEmpty());
        
        return result;
    }

    /**
     * Layer 4: Device State Validation
     * Checks target device readiness and availability
     */
    private LayerResult validateDeviceState(ActionPlan plan) {
        LayerResult result = LayerResult.builder().layerName("DEVICE_STATE").build();
        List<String> errors = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        
        String assetId = plan.getTargetAssetId();
        
        // TODO: Add real device state checks by querying IoT device registry
        // For now, we simulate basic checks
        
        // Check safety conditions from the plan
        String safetyConditions = plan.getSafetyConditions();
        if (safetyConditions != null && !safetyConditions.isEmpty()) {
            // In production, parse JSON and validate each condition
            // Example conditions: device_online, no_maintenance_mode, sensor_threshold_met
            log.debug("Safety conditions to verify: {}", safetyConditions);
            
            // Simulated validation - in production, query actual device state
            // For demonstration, we'll pass if conditions are defined
            if (safetyConditions.contains("maintenance_mode")) {
                warnings.add("Device may be in maintenance mode - verify before execution");
            }
        }
        
        // Validate action type is supported by device
        String actionType = plan.getActionType();
        if ("turn_on".equals(actionType) || "turn_off".equals(actionType)) {
            // Basic on/off actions are generally supported
            log.debug("Basic action type {} supported for asset {}", actionType, assetId);
        } else if ("adjust".equals(actionType)) {
            // Adjust actions may require additional parameter validation
            if (plan.getParameters() == null || plan.getParameters().isEmpty()) {
                warnings.add("Adjust action without parameters - using default values");
            }
        }
        
        result.setErrors(errors);
        result.setWarnings(warnings);
        result.setPassed(errors.isEmpty());
        
        return result;
    }

    // ========== Result DTOs ==========

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ValidationResult {
        private String planId;
        private String traceId;
        private boolean overallPassed;
        private String failedLayer;
        private String recommendedAction; // EXECUTE, ALERT_ONLY, REJECT
        
        private LayerResult logicalValidation;
        private LayerResult contextValidation;
        private LayerResult permissionValidation;
        private LayerResult deviceStateValidation;
        
        public List<String> getAllErrors() {
            List<String> allErrors = new ArrayList<>();
            if (logicalValidation != null) allErrors.addAll(logicalValidation.getErrors());
            if (contextValidation != null) allErrors.addAll(contextValidation.getErrors());
            if (permissionValidation != null) allErrors.addAll(permissionValidation.getErrors());
            if (deviceStateValidation != null) allErrors.addAll(deviceStateValidation.getErrors());
            return allErrors;
        }
        
        public List<String> getAllWarnings() {
            List<String> allWarnings = new ArrayList<>();
            if (logicalValidation != null) allWarnings.addAll(logicalValidation.getWarnings());
            if (contextValidation != null) allWarnings.addAll(contextValidation.getWarnings());
            if (permissionValidation != null) allWarnings.addAll(permissionValidation.getWarnings());
            if (deviceStateValidation != null) allWarnings.addAll(deviceStateValidation.getWarnings());
            return allWarnings;
        }
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class LayerResult {
        private String layerName;
        private boolean passed;
        @Builder.Default
        private List<String> errors = new ArrayList<>();
        @Builder.Default
        private List<String> warnings = new ArrayList<>();
    }
}
