package com.terraneuron.ops.service;

import com.terraneuron.ops.entity.Insight;
import com.terraneuron.ops.repository.InsightRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.Optional;

/**
 * Kafka Consumer Service for Processed Insights
 *
 * Consumes processed insights from terra-cortex AI analysis
 * Supports CloudEvents v1.0 format: terra.cortex.insight.detected
 *
 * CloudEvents format:
 * {
 *   "specversion": "1.0",
 *   "type": "terra.cortex.insight.detected",
 *   "source": "//terraneuron/terra-cortex",
 *   "id": "uuid",
 *   "time": "RFC3339",
 *   "datacontenttype": "application/json",
 *   "data": {
 *     "trace_id": "...",
 *     "farm_id": "...",
 *     "sensor_type": "...",
 *     "status": "NORMAL|ANOMALY",
 *     "severity": "info|warning|critical",
 *     "message": "...",
 *     "raw_value": 25.5,
 *     "confidence": 0.95,
 *     "detected_at": "2025-12-09T10:30:00Z",
 *     "llm_recommendation": "...",
 *     "rag_context": "..."
 *   }
 * }
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KafkaConsumerService {

    private final InsightRepository insightRepository;
    private final InsightEventParser insightEventParser;
    private final AuditService auditService;

    /**
     * Kafka listener for processed-insights topic
     * Consumes CloudEvents-compliant insight messages from terra-cortex
     */
    @KafkaListener(topics = "processed-insights", groupId = "${spring.kafka.consumer.group-id}")
    public void consumeInsight(Map<String, Object> messageData) {
        try {
            log.debug("📥 Kafka Received raw message: {}", messageData.keySet());

            // Parse the message (handles both CloudEvents and legacy formats)
            Optional<Insight> insightOpt = insightEventParser.parse(messageData);

            if (!insightOpt.isPresent()) {
                throw new IllegalArgumentException("Invalid insight event payload");
            }

            Insight insight = insightOpt.get();

            log.info("📥 Processing insight: farmId={}, status={}, message={}...",
                    insight.getFarmId(),
                    insight.getStatus(),
                    insight.getMessage() != null ?
                        insight.getMessage().substring(0, Math.min(50, insight.getMessage().length())) : "");

            // Save to database
            Insight saved = insightRepository.save(insight);
            // Legacy events do not carry a trace ID. Keep their audit records queryable
            // with a deterministic fallback tied to the newly persisted insight.
            String auditTraceId = saved.getTraceId() != null && !saved.getTraceId().isBlank()
                    ? saved.getTraceId()
                    : "insight-detected-id-" + saved.getId();
            auditService.logInsightDetected(
                    auditTraceId,
                    String.valueOf(saved.getId()),
                    saved.getFarmId(),
                    saved.getStatus(),
                    saved.getMessage());
            log.info("✅ Insight saved to database: ID={}", saved.getId());

        } catch (Exception e) {
            log.error("❌ Kafka message processing failed: {}", e.getMessage(), e);
            throw new IllegalStateException("Failed to process insight event", e);
        }
    }
}
