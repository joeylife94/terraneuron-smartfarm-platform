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

/**
 * Action Plan Controller
 * REST API for managing AI-generated action plans with human approval workflow.
 * CloudEvents v1.0 compliant with trace_id propagation.
 */
@Slf4j
@RestController
@RequestMapping("/api/actions")
@RequiredArgsConstructor
@Tag(name = "Action Plans", description = "AI-generated action plans management with safety validation")
public class ActionController {

    private final ActionPlanService actionPlanService;
    private final AuditService auditService;

    // ========== Pending Plans Endpoints ==========

    @GetMapping("/pending")
    @Operation(summary = "Get all pending action plans",
               description = "Returns all action plans awaiting human approval, ordered by priority")
    public ResponseEntity<List<ActionPlan>> getPendingPlans() {
        log.info("📋 GET /api/actions/pending");
        List<ActionPlan> plans = actionPlanService.getPendingPlans();
        return ResponseEntity.ok(plans);
    }

    @GetMapping("/pending/paged")
    @Operation(summary = "Get pending plans with pagination")
    public ResponseEntity<Page<ActionPlan>> getPendingPlansPaged(
            @Parameter(description = "Page number (0-indexed)") @RequestParam(defaultValue = "0") int page,
            @Parameter(description = "Page size") @RequestParam(defaultValue = "20") int size) {
        log.info("📋 GET /api/actions/pending/paged - page={}, size={}", page, size);
        Pageable pageable = PageRequest.of(page, size);
        Page<ActionPlan> plans = actionPlanService.getPendingPlans(pageable);
        return ResponseEntity.ok(plans);
    }

    @GetMapping("/pending/farm/{farmId}")
    @Operation(summary = "Get pending plans for a specific farm")
    public ResponseEntity<List<ActionPlan>> getPendingPlansByFarm(
            @Parameter(description = "Farm ID") @PathVariable String farmId) {
        log.info("📋 GET /api/actions/pending/farm/{}", farmId);
        List<ActionPlan> plans = actionPlanService.getPendingPlansByFarm(farmId);
        return ResponseEntity.ok(plans);
    }

    // ========== Plan Details Endpoint ==========

    @GetMapping("/{planId}")
    @Operation(summary = "Get action plan details by ID")
    public ResponseEntity<ActionPlan> getPlanById(
            @Parameter(description = "Plan ID") @PathVariable String planId) {
        log.info("📋 GET /api/actions/{}", planId);
        return actionPlanService.getPlanById(planId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    // ========== Approval/Rejection Endpoints ==========

    @PostMapping("/{planId}/approve")
    @Operation(summary = "Approve an action plan",
               description = "Approves the plan and runs configured safety validation before execution")
    public ResponseEntity<?> approvePlan(
            @Parameter(description = "Plan ID") @PathVariable String planId,
            @RequestBody ApprovalRequest request,
            Principal principal) {
        String actor = principal.getName();
        log.info("✅ POST /api/actions/{}/approve by {}", planId, actor);

        try {
            ActionPlan approvedPlan = actionPlanService.approvePlan(
                    planId,
                    actor,
                    request.getNotes()
            );

            return approvalResponse(approvedPlan);

        } catch (IllegalArgumentException e) {
            return ResponseEntity.notFound().build();
        } catch (IllegalStateException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "status", "error",
                    "message", e.getMessage()
            ));
        }
    }

    @PostMapping("/{planId}/reject")
    @Operation(summary = "Reject an action plan")
    public ResponseEntity<?> rejectPlan(
            @Parameter(description = "Plan ID") @PathVariable String planId,
            @RequestBody RejectionRequest request,
            Principal principal) {
        String actor = principal.getName();
        log.info("❌ POST /api/actions/{}/reject by {}", planId, actor);

        try {
            ActionPlan rejectedPlan = actionPlanService.rejectPlan(
                    planId,
                    actor,
                    request.getReason()
            );

            return ResponseEntity.ok(Map.of(
                    "status", "rejected",
                    "message", "Plan rejected",
                    "planStatus", rejectedPlan.getStatus().name(),
                    "plan", rejectedPlan
            ));

        } catch (IllegalArgumentException e) {
            return ResponseEntity.notFound().build();
        } catch (IllegalStateException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "status", "error",
                    "message", e.getMessage()
            ));
        }
    }

    private ResponseEntity<?> approvalResponse(ActionPlan plan) {
        String planStatus = plan.getStatus().name();
        String responseStatus = planStatus.toLowerCase(Locale.ROOT);

        if (plan.getStatus() == ActionPlan.PlanStatus.REJECTED) {
            return ResponseEntity.unprocessableEntity().body(Map.of(
                    "status", responseStatus,
                    "message", "Plan rejected by safety validation",
                    "planStatus", planStatus,
                    "reason", defaultIfBlank(plan.getRejectionReason(), "Safety validation rejected the plan"),
                    "plan", plan
            ));
        }

        if (plan.getStatus() == ActionPlan.PlanStatus.FAILED) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of(
                    "status", responseStatus,
                    "message", "Plan approval completed but execution failed",
                    "planStatus", planStatus,
                    "error", defaultIfBlank(plan.getExecutionError(), "Execution failed without an error message"),
                    "plan", plan
            ));
        }

        return ResponseEntity.ok(Map.of(
                "status", responseStatus,
                "message", "Plan approval completed",
                "planStatus", planStatus,
                "plan", plan
        ));
    }

    private String defaultIfBlank(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    // ========== Statistics Endpoint ==========

    @GetMapping("/statistics")
    @Operation(summary = "Get action plan statistics")
    public ResponseEntity<Map<String, Long>> getStatistics() {
        log.info("📊 GET /api/actions/statistics");
        return ResponseEntity.ok(actionPlanService.getPlanStatistics());
    }

    // ========== Audit Trail Endpoints ==========

    @GetMapping("/{planId}/audit")
    @Operation(summary = "Get audit trail for a specific plan")
    public ResponseEntity<List<AuditLog>> getPlanAuditTrail(
            @Parameter(description = "Plan ID") @PathVariable String planId) {
        log.info("📝 GET /api/actions/{}/audit", planId);
        List<AuditLog> auditTrail = auditService.getPlanHistory(planId);
        return ResponseEntity.ok(auditTrail);
    }

    @GetMapping("/audit/trace/{traceId}")
    @Operation(summary = "Get complete audit trail by trace ID",
               description = "Returns all audit events for a distributed trace")
    public ResponseEntity<List<AuditLog>> getAuditTrailByTrace(
            @Parameter(description = "Trace ID for distributed tracing") @PathVariable String traceId) {
        log.info("📝 GET /api/actions/audit/trace/{}", traceId);
        List<AuditLog> auditTrail = auditService.getAuditTrail(traceId);
        return ResponseEntity.ok(auditTrail);
    }

    // ========== Request/Response DTOs ==========

    @lombok.Data
    public static class ApprovalRequest {
        private String notes;
    }

    @lombok.Data
    public static class RejectionRequest {
        private String reason;
    }
}
