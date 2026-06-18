package com.terraneuron.ops.service;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for ActionPlanEventValidator
 * Tests CloudEvents v1.0 envelope validation for action plan events
 */
class ActionPlanEventValidatorTest {
    
    private ActionPlanEventValidator validator;
    
    @BeforeEach
    void setUp() {
        validator = new ActionPlanEventValidator();
    }
    
    /**
     * Test: Validate a valid CloudEvents v1.0 action plan event
     */
    @Test
    void testValidateValidActionPlanEvent() {
        Map<String, Object> event = createValidActionPlanEvent();
        
        Optional<Map<String, Object>> result = validator.validate(event);
        
        assertTrue(result.isPresent());
        Map<String, Object> data = result.get();
        assertEquals("plan-abc12345", data.get("plan_id"));
        assertEquals("farm-001", data.get("farm_id"));
        assertEquals("ventilation", data.get("action_category"));
    }
    
    /**
     * Test: Validate event with missing specversion
     */
    @Test
    void testValidateEventMissingSpecVersion() {
        Map<String, Object> event = createValidActionPlanEvent();
        event.remove("specversion");
        
        Optional<Map<String, Object>> result = validator.validate(event);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Validate event with wrong specversion
     */
    @Test
    void testValidateEventWrongSpecVersion() {
        Map<String, Object> event = createValidActionPlanEvent();
        event.put("specversion", "2.0");

        Optional<Map<String, Object>> result = validator.validate(event);

        assertFalse(result.isPresent());
    }

    /**
     * Test: Validate event with non-string specversion
     */
    @Test
    void testValidateEventSpecVersionNotString() {
        Map<String, Object> event = createValidActionPlanEvent();
        event.put("specversion", 1.0);

        Optional<Map<String, Object>> result = validator.validate(event);

        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Validate event with missing type
     */
    @Test
    void testValidateEventMissingType() {
        Map<String, Object> event = createValidActionPlanEvent();
        event.remove("type");
        
        Optional<Map<String, Object>> result = validator.validate(event);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Validate event with wrong type
     */
    @Test
    void testValidateEventWrongType() {
        Map<String, Object> event = createValidActionPlanEvent();
        event.put("type", "terra.ops.alert.triggered");

        Optional<Map<String, Object>> result = validator.validate(event);

        assertFalse(result.isPresent());
    }

    /**
     * Test: Validate event with non-string type
     */
    @Test
    void testValidateEventTypeNotString() {
        Map<String, Object> event = createValidActionPlanEvent();
        event.put("type", 123);

        Optional<Map<String, Object>> result = validator.validate(event);

        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Validate event with missing data field
     */
    @Test
    void testValidateEventMissingData() {
        Map<String, Object> event = createValidActionPlanEvent();
        event.remove("data");
        
        Optional<Map<String, Object>> result = validator.validate(event);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Validate event with empty data
     */
    @Test
    void testValidateEventEmptyData() {
        Map<String, Object> event = createValidActionPlanEvent();
        event.put("data", new HashMap<>());
        
        Optional<Map<String, Object>> result = validator.validate(event);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Validate event with data as non-map (string)
     */
    @Test
    void testValidateEventDataNotMap() {
        Map<String, Object> event = createValidActionPlanEvent();
        event.put("data", "not a map");
        
        Optional<Map<String, Object>> result = validator.validate(event);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Validate event with data as non-map (list)
     */
    @Test
    void testValidateEventDataList() {
        Map<String, Object> event = createValidActionPlanEvent();
        event.put("data", java.util.Arrays.asList("item1", "item2"));
        
        Optional<Map<String, Object>> result = validator.validate(event);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Validate null event
     */
    @Test
    void testValidateNullEvent() {
        Optional<Map<String, Object>> result = validator.validate(null);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Extract trace_id from valid event
     */
    @Test
    void testExtractTraceIdFromValidEvent() {
        Map<String, Object> event = createValidActionPlanEvent();
        
        Optional<String> traceId = validator.extractTraceId(event);
        
        assertTrue(traceId.isPresent());
        assertEquals("trace-uuid-123", traceId.get());
    }
    
    /**
     * Test: Extract trace_id from event missing trace_id
     */
    @Test
    void testExtractTraceIdMissing() {
        Map<String, Object> event = createValidActionPlanEvent();
        
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) event.get("data");
        data.remove("trace_id");
        
        Optional<String> traceId = validator.extractTraceId(event);
        
        assertFalse(traceId.isPresent());
    }
    
    /**
     * Test: Extract trace_id from null event
     */
    @Test
    void testExtractTraceIdFromNullEvent() {
        Optional<String> traceId = validator.extractTraceId(null);
        
        assertFalse(traceId.isPresent());
    }
    
    /**
     * Test: Validate event preserves all data fields
     */
    @Test
    void testValidatePreservesAllDataFields() {
        Map<String, Object> event = createValidActionPlanEvent();
        
        @SuppressWarnings("unchecked")
        Map<String, Object> originalData = (Map<String, Object>) event.get("data");
        int originalFieldCount = originalData.size();
        
        Optional<Map<String, Object>> result = validator.validate(event);
        
        assertTrue(result.isPresent());
        Map<String, Object> validatedData = result.get();
        assertEquals(originalFieldCount, validatedData.size());
        assertEquals("turn_on", validatedData.get("action_type"));
        assertEquals("High priority action plan", validatedData.get("reasoning"));
    }
    
    // ────── Helper Methods ──────
    
    /**
     * Create a valid CloudEvents v1.0 action plan event
     */
    private Map<String, Object> createValidActionPlanEvent() {
        Map<String, Object> event = new HashMap<>();
        event.put("specversion", "1.0");
        event.put("type", "terra.cortex.plan.generated");
        event.put("source", "//terraneuron/terra-cortex");
        event.put("id", "evt-uuid-456");
        event.put("time", "2025-12-09T10:30:00Z");
        event.put("datacontenttype", "application/json");
        event.put("data", createValidActionPlanData());
        return event;
    }
    
    /**
     * Create valid action plan data payload
     */
    private Map<String, Object> createValidActionPlanData() {
        Map<String, Object> data = new HashMap<>();
        data.put("trace_id", "trace-uuid-123");
        data.put("plan_id", "plan-abc12345");
        data.put("plan_type", "input");
        data.put("farm_id", "farm-001");
        data.put("target_asset_id", "fan-01");
        data.put("target_asset_type", "device");
        data.put("action_category", "ventilation");
        data.put("action_type", "turn_on");
        data.put("parameters", Map.of("duration_minutes", 30, "speed_level", "high"));
        data.put("reasoning", "High priority action plan");
        data.put("requires_approval", true);
        data.put("priority", "high");
        data.put("generated_at", "2025-12-09T10:30:00Z");
        data.put("safety_conditions", java.util.Arrays.asList("temperature < 50C", "humidity < 80%"));
        return data;
    }
}
