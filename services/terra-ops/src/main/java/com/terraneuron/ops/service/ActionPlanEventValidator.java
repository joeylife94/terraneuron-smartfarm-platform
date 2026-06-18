package com.terraneuron.ops.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Optional;

/**
 * Validator for CloudEvents v1.0 Action Plan Events
 * 
 * Validates incoming action plan events from terra-cortex with strict envelope checks:
 * - specversion must be "1.0"
 * - type must be "terra.cortex.plan.generated"
 * - data field must exist and be a non-empty object
 * 
 * Follows CloudEvents v1.0 specification.
 * See docs/contracts/action-plan.schema.json for the canonical schema.
 */
@Slf4j
@Component
public class ActionPlanEventValidator {
    
    private static final String EXPECTED_SPEC_VERSION = "1.0";
    private static final String EXPECTED_EVENT_TYPE = "terra.cortex.plan.generated";
    private static final String EXPECTED_SOURCE = "//terraneuron/terra-cortex";
    
    /**
     * Validate a CloudEvents action plan envelope
     * 
     * @param event Raw event map from Kafka
     * @return Optional containing the extracted data map if valid, empty if validation fails
     */
    public Optional<Map<String, Object>> validate(Map<String, Object> event) {
        if (event == null) {
            log.warn("Cannot validate null action plan event");
            return Optional.empty();
        }
        
        // Validate specversion
        Object specversionObj = event.get("specversion");
        if (specversionObj == null) {
            log.error("❌ Action plan CloudEvent missing 'specversion' field");
            return Optional.empty();
        }

        if (!(specversionObj instanceof String)) {
            log.error("❌ Action plan CloudEvent 'specversion' field is not a string: type={}",
                    specversionObj.getClass().getName());
            return Optional.empty();
        }

        String specversion = (String) specversionObj;
        if (!specversion.equals(EXPECTED_SPEC_VERSION)) {
            log.error("❌ Invalid CloudEvents specversion for action plan: expected={}, received={}",
                    EXPECTED_SPEC_VERSION, specversion);
            return Optional.empty();
        }
        
        // Validate type
        Object typeObj = event.get("type");
        if (typeObj == null) {
            log.error("❌ Action plan CloudEvent missing 'type' field");
            return Optional.empty();
        }

        if (!(typeObj instanceof String)) {
            log.error("❌ Action plan CloudEvent 'type' field is not a string: type={}",
                    typeObj.getClass().getName());
            return Optional.empty();
        }

        String type = (String) typeObj;
        if (!type.equals(EXPECTED_EVENT_TYPE)) {
            log.warn("⚠️ Skipping event with unexpected type for action plan: received={}", type);
            return Optional.empty();
        }
        
        // Validate data exists and is a non-empty object
        Object dataObj = event.get("data");
        if (dataObj == null) {
            log.error("❌ Action plan CloudEvent missing 'data' field");
            return Optional.empty();
        }
        
        if (!(dataObj instanceof Map)) {
            log.error("❌ Action plan CloudEvent 'data' field is not a map: type={}", dataObj.getClass().getName());
            return Optional.empty();
        }
        
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) dataObj;
        
        if (data.isEmpty()) {
            log.error("❌ Action plan CloudEvent 'data' field is empty");
            return Optional.empty();
        }
        
        // All validations passed
        log.info("✅ Valid CloudEvents action plan envelope: type={}, has {} fields in data", 
                type, data.size());
        
        return Optional.of(data);
    }
    
    /**
     * Extract trace_id from action plan event for distributed tracing
     * 
     * @param event Raw event map from Kafka
     * @return Optional containing trace_id if present, empty otherwise
     */
    public Optional<String> extractTraceId(Map<String, Object> event) {
        if (event == null) {
            return Optional.empty();
        }
        
        Object dataObj = event.get("data");
        if (dataObj instanceof Map) {
            @SuppressWarnings("unchecked")
            Map<String, Object> data = (Map<String, Object>) dataObj;
            Object traceId = data.get("trace_id");
            if (traceId instanceof String) {
                return Optional.of((String) traceId);
            }
        }
        
        return Optional.empty();
    }
}
