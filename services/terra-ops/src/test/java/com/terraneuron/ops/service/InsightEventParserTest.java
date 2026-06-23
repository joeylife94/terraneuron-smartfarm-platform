package com.terraneuron.ops.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.Insight;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for InsightEventParser
 * Tests CloudEvents parsing, legacy format support, and error handling
 */
class InsightEventParserTest {
    
    private InsightEventParser parser;
    private ObjectMapper objectMapper;
    
    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();
        parser = new InsightEventParser(objectMapper);
    }
    
    /**
     * Test: Parse valid CloudEvents v1.0 insight message
     */
    @Test
    void testParseValidCloudEventsInsight() {
        Map<String, Object> messageData = createValidCloudEventsMessage();
        
        Optional<Insight> result = parser.parse(messageData);
        
        assertTrue(result.isPresent());
        Insight insight = result.get();
        
        assertEquals("trace-uuid-123", insight.getTraceId());
        assertEquals("farm-001", insight.getFarmId());
        assertEquals("sensor-temp-01", insight.getAssetId());
        assertEquals("sensor", insight.getAssetType());
        assertEquals("temperature", insight.getSensorType());
        assertEquals("ANOMALY", insight.getStatus());
        assertEquals("critical", insight.getSeverity());
        assertEquals(42.5, insight.getRawValue());
        assertEquals(0.95, insight.getConfidence());
        assertEquals("Temperature 42.5°C exceeds threshold", insight.getMessage());
        assertEquals("High temperature detected by sensor", insight.getLlmRecommendation());
        assertEquals("Similar incidents on record", insight.getRagContext());
        assertNotNull(insight.getTimestamp());
    }
    
    /**
     * Test: Parse CloudEvents message missing 'data' field
     */
    @Test
    void testParseCloudEventsMissingData() {
        Map<String, Object> messageData = new HashMap<>();
        messageData.put("specversion", "1.0");
        messageData.put("type", "terra.cortex.insight.detected");
        messageData.put("source", "//terraneuron/terra-cortex");
        messageData.put("id", "uuid-123");
        messageData.put("time", "2025-12-09T10:30:00Z");
        messageData.put("datacontenttype", "application/json");
        // Missing 'data' field
        
        Optional<Insight> result = parser.parse(messageData);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Parse CloudEvents message with empty data
     */
    @Test
    void testParseCloudEventsEmptyData() {
        Map<String, Object> messageData = new HashMap<>();
        messageData.put("specversion", "1.0");
        messageData.put("type", "terra.cortex.insight.detected");
        messageData.put("source", "//terraneuron/terra-cortex");
        messageData.put("id", "uuid-123");
        messageData.put("time", "2025-12-09T10:30:00Z");
        messageData.put("datacontenttype", "application/json");
        messageData.put("data", new HashMap<>());
        
        Optional<Insight> result = parser.parse(messageData);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Parse CloudEvents message with invalid confidence value
     */
    @Test
    void testParseCloudEventsInvalidConfidence() {
        Map<String, Object> messageData = createValidCloudEventsMessage();
        
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) messageData.get("data");
        data.put("confidence", 1.5); // Invalid: > 1
        
        Optional<Insight> result = parser.parse(messageData);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Parse CloudEvents message missing required field (farmId)
     */
    @Test
    void testParseCloudEventsMissingFarmId() {
        Map<String, Object> messageData = createValidCloudEventsMessage();
        
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) messageData.get("data");
        data.remove("farm_id");
        
        Optional<Insight> result = parser.parse(messageData);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Parse legacy flat format message
     */
    @Test
    void testParseLegacyFlatFormat() {
        Map<String, Object> messageData = new HashMap<>();
        messageData.put("farmId", "farm-002");
        messageData.put("sensorType", "humidity");
        messageData.put("status", "NORMAL");
        messageData.put("severity", "info");
        messageData.put("message", "Humidity within normal range");
        messageData.put("confidence", 0.98);
        messageData.put("rawValue", 65.0);
        messageData.put("detectedAt", "2025-12-09T10:30:00Z");
        messageData.put("llmRecommendation", "No action needed");
        
        Optional<Insight> result = parser.parse(messageData);
        
        assertTrue(result.isPresent());
        Insight insight = result.get();
        
        assertEquals("farm-002", insight.getFarmId());
        assertEquals("humidity", insight.getSensorType());
        assertEquals("NORMAL", insight.getStatus());
        assertEquals("info", insight.getSeverity());
        assertEquals(65.0, insight.getRawValue());
        assertEquals(0.98, insight.getConfidence());
        assertEquals("Humidity within normal range", insight.getMessage());
    }
    
    /**
     * Test: Parse legacy format missing required field (farmId)
     */
    @Test
    void testParseLegacyMissingFarmId() {
        Map<String, Object> messageData = new HashMap<>();
        messageData.put("sensorType", "temperature");
        messageData.put("status", "ANOMALY");
        messageData.put("message", "Temperature high");
        
        Optional<Insight> result = parser.parse(messageData);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Parse null message
     */
    @Test
    void testParseNullMessage() {
        Optional<Insight> result = parser.parse(null);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Parse malformed message (neither CloudEvents nor legacy)
     */
    @Test
    void testParseMalformedMessage() {
        Map<String, Object> messageData = new HashMap<>();
        messageData.put("unknownField", "value");
        messageData.put("anotherField", 123);
        
        Optional<Insight> result = parser.parse(messageData);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Parse CloudEvents with wrong event type
     */
    @Test
    void testParseCloudEventsWrongType() {
        Map<String, Object> messageData = new HashMap<>();
        messageData.put("specversion", "1.0");
        messageData.put("type", "terra.ops.alert.triggered"); // Wrong type
        messageData.put("source", "//terraneuron/terra-ops");
        messageData.put("id", "uuid-123");
        messageData.put("time", "2025-12-09T10:30:00Z");
        messageData.put("datacontenttype", "application/json");
        messageData.put("data", createValidDataPayload());
        
        Optional<Insight> result = parser.parse(messageData);
        
        assertFalse(result.isPresent());
    }
    
    /**
     * Test: Timestamp parsing with ISO format
     */
    @Test
    void testTimestampParsingIsoFormat() {
        Map<String, Object> messageData = createValidCloudEventsMessage();
        
        Optional<Insight> result = parser.parse(messageData);
        
        assertTrue(result.isPresent());
        assertNotNull(result.get().getTimestamp());
    }
    
    /**
     * Test: Timestamp parsing with null value uses current time
     */
    @Test
    void testTimestampParsingNullValue() {
        Map<String, Object> messageData = createValidCloudEventsMessage();
        
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) messageData.get("data");
        data.put("detected_at", null);
        
        Optional<Insight> result = parser.parse(messageData);
        
        assertTrue(result.isPresent());
        assertNotNull(result.get().getTimestamp());
    }
    
    /**
     * Test: CloudEvents message with optional fields
     */
    @Test
    void testParseCloudEventsWithOptionalFields() {
        Map<String, Object> messageData = createValidCloudEventsMessage();
        
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) messageData.get("data");
        data.put("llm_recommendation", null);
        data.put("rag_context", null);
        
        Optional<Insight> result = parser.parse(messageData);
        
        assertTrue(result.isPresent());
        Insight insight = result.get();
        assertNull(insight.getLlmRecommendation());
    }
    
    // ────── Helper Methods ──────
    
    private Map<String, Object> createValidCloudEventsMessage() {
        Map<String, Object> messageData = new HashMap<>();
        messageData.put("specversion", "1.0");
        messageData.put("type", "terra.cortex.insight.detected");
        messageData.put("source", "//terraneuron/terra-cortex");
        messageData.put("id", "a1b2c3d4-e5f6-7890-abcd-ef1234567890");
        messageData.put("time", "2025-12-09T10:30:00Z");
        messageData.put("datacontenttype", "application/json");
        messageData.put("data", createValidDataPayload());
        return messageData;
    }
    
    private Map<String, Object> createValidDataPayload() {
        Map<String, Object> data = new HashMap<>();
        data.put("trace_id", "trace-uuid-123");
        data.put("farm_id", "farm-001");
        data.put("asset_id", "sensor-temp-01");
        data.put("asset_type", "sensor");
        data.put("sensor_type", "temperature");
        data.put("status", "ANOMALY");
        data.put("severity", "critical");
        data.put("message", "Temperature 42.5°C exceeds threshold");
        data.put("raw_value", 42.5);
        data.put("confidence", 0.95);
        data.put("detected_at", "2025-12-09T10:30:00Z");
        data.put("llm_recommendation", "High temperature detected by sensor");
        data.put("rag_context", "Similar incidents on record");
        return data;
    }
}
