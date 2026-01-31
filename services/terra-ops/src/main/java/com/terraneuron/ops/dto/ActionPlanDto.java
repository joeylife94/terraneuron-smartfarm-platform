package com.terraneuron.ops.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * CloudEvents-compliant Action Plan DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ActionPlanDto {
    
    // CloudEvents fields
    private String specversion;
    private String type;
    private String source;
    private String id;
    private String time;
    private String datacontenttype;
    
    // Data payload
    private ActionPlanData data;
    
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ActionPlanData {
        private String traceId;
        private String planId;
        private String planType;
        private String farmId;
        private String targetAssetId;
        private String targetAssetType;
        private String actionCategory;
        private String actionType;
        private Map<String, Object> parameters;
        private String reasoning;
        private boolean requiresApproval;
        private String priority;
        private String estimatedImpact;
        private List<String> safetyConditions;
        private Instant generatedAt;
        private Instant expiresAt;
    }
}
