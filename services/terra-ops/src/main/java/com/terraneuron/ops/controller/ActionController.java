package com.terraneuron.ops.controller;

import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.entity.AuditLog;
import com.terraneuron.ops.service.ActionPlanService;
import com.terraneuron.ops.service.AuditService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.security.Principal;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@RestController
@RequestMapping("/api/actions")
@RequiredArgsConstructor
@Slf4j
@Tag(name = "Action Plans", description = "AI-generated plans with approval and device safety gating")
public class ActionController {

    private final ActionPlanService actionPlanService;
    private final AuditService auditService;

    @GetMapping("/pending")
    public ResponseEntity<List<ActionPlan>> getPendingPlans() {
        return ResponseEntity.ok(actionPlanService.getPendingPlans());
    }

    @GetMapping("/safety-blocked")
    @Operation(summary = "Get approved plans waiting for device safety revalidation")
    public ResponseEntity<List<ActionPlan>> getSafetyBlockedPlans() {
        return ResponseEntity.ok(actionPlanService.getSafetyBlockedPlans());
    }

    @GetMapping("/pending/paged")
    public ResponseEntity<Page<ActionPlan>> getPendingPlansPaged(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        Pageable pageable = PageRequest.of(page, size);
        return ResponseEntity.ok(actionPlanService.getPendingPlans(pageable));
    }

    @GetMapping("/pending/farm/{farmId}")
    public ResponseEntity<List<ActionPlan>> getPendingPlansByFarm(@PathVariable String farmId) {
        return ResponseEntity.ok(actionPlanService.getPendingPlansByFarm(farmId));
    }

    @GetMapping("/{planId}")
    public ResponseEntity<ActionPlan> getPlanById(@PathVariable String planId) {
        return actionPlanService.getPlanById(planId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/{planId}/approve")
    public ResponseEntity<?> approvePlan(
            @PathVariable String planId,
            @RequestBody ApprovalRequest request,
            Principal principal) {
        try {
            return lifecycleResponse(actionPlanService.approvePlan(
                    planId, principal.getName(), request.getNotes()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.notFound().build();
        } catch (IllegalStateException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "status", "error",
                    "message", e.getMessage()));
        }
    }

    @PostMapping("/{planId}/safety/revalidate")
    @Operation(summary = "Revalidate an already approved plan after a transient device safety block")
    public ResponseEntity<?> revalidateSafety(@PathVariable String planId) {
        try {
            return lifecycleResponse(actionPlanService.revalidateSafety(planId));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.notFound().build();
        } catch (IllegalStateException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "status", "error",
                    "message", e.getMessage()));
        }
    }

    @PostMapping("/{planId}/reject")
    public ResponseEntity<?> rejectPlan(
            @PathVariable String planId,
            @RequestBody RejectionRequest request,
            Principal principal) {
        try {
            ActionPlan plan = actionPlanService.rejectPlan(
                    planId, principal.getName(), request.getReason());
            return ResponseEntity.ok(Map.of(
                    "status", "rejected",
                    "message", "Plan rejected",
                    "planStatus", plan.getStatus().name(),
                    "plan", plan));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.notFound().build();
        } catch (IllegalStateException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "status", "error",
                    "message", e.getMessage()));
        }
    }

    private ResponseEntity<?> lifecycleResponse(ActionPlan plan) {
        String planStatus = plan.getStatus().name();
        String responseStatus = planStatus.toLowerCase(Locale.ROOT);
        if (plan.getStatus() == ActionPlan.PlanStatus.SAFETY_BLOCKED) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of(
                    "status", responseStatus,
                    "message", "Approved plan is blocked pending device safety revalidation",
                    "planStatus", planStatus,
                    "reasonCode", defaultIfBlank(
                            plan.getSafetyBlockReasonCode(), "DEVICE_SAFETY_BLOCKED"),
                    "plan", plan));
        }
        if (plan.getStatus() == ActionPlan.PlanStatus.REJECTED) {
            return ResponseEntity.unprocessableEntity().body(Map.of(
                    "status", responseStatus,
                    "message", "Plan rejected by safety validation",
                    "planStatus", planStatus,
                    "reason", defaultIfBlank(
                            plan.getRejectionReason(), "Safety validation rejected the plan"),
                    "plan", plan));
        }
        if (plan.getStatus() == ActionPlan.PlanStatus.FAILED) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of(
                    "status", responseStatus,
                    "message", "Plan approval completed but execution failed",
                    "planStatus", planStatus,
                    "error", defaultIfBlank(plan.getExecutionError(), "Execution failed"),
                    "plan", plan));
        }
        return ResponseEntity.ok(Map.of(
                "status", responseStatus,
                "message", "Plan approval lifecycle updated",
                "planStatus", planStatus,
                "plan", plan));
    }

    @GetMapping("/statistics")
    public ResponseEntity<Map<String, Long>> getStatistics() {
        return ResponseEntity.ok(actionPlanService.getPlanStatistics());
    }

    @GetMapping("/{planId}/audit")
    public ResponseEntity<List<AuditLog>> getPlanAuditTrail(@PathVariable String planId) {
        return ResponseEntity.ok(auditService.getPlanHistory(planId));
    }

    @GetMapping("/audit/trace/{traceId}")
    public ResponseEntity<List<AuditLog>> getAuditTrailByTrace(@PathVariable String traceId) {
        return ResponseEntity.ok(auditService.getAuditTrail(traceId));
    }

    private String defaultIfBlank(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    @lombok.Data
    public static class ApprovalRequest {
        private String notes;
    }

    @lombok.Data
    public static class RejectionRequest {
        private String reason;
    }
}
