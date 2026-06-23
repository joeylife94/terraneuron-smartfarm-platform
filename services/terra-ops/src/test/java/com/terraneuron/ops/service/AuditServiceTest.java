package com.terraneuron.ops.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.AuditLog;
import com.terraneuron.ops.repository.AuditLogRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for AuditService
 * Focuses on safe trace ID handling in log output.
 */
@ExtendWith(MockitoExtension.class)
class AuditServiceTest {

    @Mock
    private AuditLogRepository auditLogRepository;

    @Mock
    private ObjectMapper objectMapper;

    @InjectMocks
    private AuditService auditService;

    @Test
    void logInsightDetected_WithShortTraceId_DoesNotThrow() throws Exception {
        // Arrange: Create an insight with a short trace ID (shorter than 20 chars)
        String shortTraceId = "short-trace";
        String insightId = "42";
        String farmId = "farm-1";
        String status = "NORMAL";
        String message = "test message";

        AuditLog savedLog = AuditLog.builder()
                .traceId(shortTraceId)
                .eventType(AuditLog.EventType.INSIGHT_DETECTED)
                .entityType("insight")
                .entityId(insightId)
                .actor("system")
                .action("Insight detected: " + status + " - " + message)
                .timestamp(Instant.now())
                .success(true)
                .build();

        when(auditLogRepository.save(any(AuditLog.class))).thenReturn(savedLog);
        when(objectMapper.writeValueAsString(any())).thenReturn("{}");

        // Act: Call logInsightDetected with short trace ID
        AuditLog result = auditService.logInsightDetected(shortTraceId, insightId, farmId, status, message);

        // Assert: Verify no exception is thrown and the saved log has the exact trace ID
        assertThat(result).isNotNull();
        assertThat(result.getTraceId()).isEqualTo(shortTraceId);

        ArgumentCaptor<AuditLog> logCaptor = ArgumentCaptor.forClass(AuditLog.class);
        verify(auditLogRepository).save(logCaptor.capture());
        AuditLog capturedLog = logCaptor.getValue();
        assertThat(capturedLog.getTraceId()).isEqualTo(shortTraceId);
    }

    @Test
    void logInsightDetected_WithNullTraceId_DoesNotThrow() throws Exception {
        // Arrange: Create an insight with null trace ID
        String insightId = "42";
        String farmId = "farm-1";
        String status = "ANOMALY";
        String message = "anomaly detected";

        AuditLog savedLog = AuditLog.builder()
                .traceId(null)
                .eventType(AuditLog.EventType.INSIGHT_DETECTED)
                .entityType("insight")
                .entityId(insightId)
                .actor("system")
                .action("Insight detected: " + status + " - " + message)
                .timestamp(Instant.now())
                .success(true)
                .build();

        when(auditLogRepository.save(any(AuditLog.class))).thenReturn(savedLog);
        when(objectMapper.writeValueAsString(any())).thenReturn("{}");

        // Act: Call logInsightDetected with null trace ID
        AuditLog result = auditService.logInsightDetected(null, insightId, farmId, status, message);

        // Assert: Verify no exception is thrown and the saved log persists null
        assertThat(result).isNotNull();
        assertThat(result.getTraceId()).isNull();

        ArgumentCaptor<AuditLog> logCaptor = ArgumentCaptor.forClass(AuditLog.class);
        verify(auditLogRepository).save(logCaptor.capture());
        AuditLog capturedLog = logCaptor.getValue();
        assertThat(capturedLog.getTraceId()).isNull();
    }

    @Test
    void logInsightDetected_WithLongTraceId_PreservesFullValue() throws Exception {
        // Arrange: Create an insight with a long trace ID (longer than 20 chars)
        String longTraceId = "trace-a1b2c3d4-e5f6-7890-abcd-ef1234567890";
        String insightId = "99";
        String farmId = "farm-2";
        String status = "NORMAL";
        String message = "long trace test";

        AuditLog savedLog = AuditLog.builder()
                .traceId(longTraceId)
                .eventType(AuditLog.EventType.INSIGHT_DETECTED)
                .entityType("insight")
                .entityId(insightId)
                .actor("system")
                .action("Insight detected: " + status + " - " + message)
                .timestamp(Instant.now())
                .success(true)
                .build();

        when(auditLogRepository.save(any(AuditLog.class))).thenReturn(savedLog);
        when(objectMapper.writeValueAsString(any())).thenReturn("{}");

        // Act: Call logInsightDetected with long trace ID
        AuditLog result = auditService.logInsightDetected(longTraceId, insightId, farmId, status, message);

        // Assert: Verify the full trace ID is preserved in persisted log
        assertThat(result).isNotNull();
        assertThat(result.getTraceId()).isEqualTo(longTraceId);

        ArgumentCaptor<AuditLog> logCaptor = ArgumentCaptor.forClass(AuditLog.class);
        verify(auditLogRepository).save(logCaptor.capture());
        AuditLog capturedLog = logCaptor.getValue();
        assertThat(capturedLog.getTraceId()).isEqualTo(longTraceId);
    }
}
