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
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
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
               description = "Approves the plan and triggers execution after 4-layer safety validation")
    public ResponseEntity<?> approvePlan(
            @Parameter(description = "Plan ID") @PathVariable String planId,
            @RequestBody ApprovalRequest request) {
        log.info("✅ POST /api/actions/{}/approve by {}", planId, request.getApprovedBy());
        
        try {
            ActionPlan approvedPlan = actionPlanService.approvePlan(
                    planId, 
                    request.getApprovedBy(), 
                    request.getNotes()
            );
            
            return ResponseEntity.ok(Map.of(
                    "status", "success",
                    "message", "Plan approved and executed",
                    "plan", approvedPlan
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

    @PostMapping("/{planId}/reject")
    @Operation(summary = "Reject an action plan")
    public ResponseEntity<?> rejectPlan(
            @Parameter(description = "Plan ID") @PathVariable String planId,
            @RequestBody RejectionRequest request) {
        log.info("❌ POST /api/actions/{}/reject by {}", planId, request.getRejectedBy());
        
        try {
            ActionPlan rejectedPlan = actionPlanService.rejectPlan(
                    planId, 
                    request.getRejectedBy(), 
                    request.getReason()
            );
            
            return ResponseEntity.ok(Map.of(
                    "status", "success",
                    "message", "Plan rejected",
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
        private String approvedBy;
        private String notes;
    }

    @lombok.Data
    public static class RejectionRequest {
        private String rejectedBy;
        private String reason;
    }
}
