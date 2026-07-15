package com.terraneuron.ops.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.Insight;
import com.terraneuron.ops.repository.ActionPlanRepository;
import com.terraneuron.ops.repository.InsightRepository;
import com.terraneuron.ops.service.safety.SafetyValidator;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.core.KafkaTemplate;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class KafkaListenerFailurePropagationTest {

    @Test
    void insightListenerPropagatesInvalidPayloadFailure() {
        InsightRepository repository = mock(InsightRepository.class);
        InsightEventParser parser = mock(InsightEventParser.class);
        AuditService auditService = mock(AuditService.class);
        Map<String, Object> invalidEvent = Map.of("unexpected", "payload");
        when(parser.parse(invalidEvent)).thenReturn(Optional.empty());
        KafkaConsumerService consumer = new KafkaConsumerService(
                repository, parser, auditService, contractSchemaValidator());

        assertThatThrownBy(() -> consumer.consumeInsight(invalidEvent))
                .isInstanceOf(IllegalStateException.class)
                .hasCauseInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void actionPlanListenerPropagatesValidationFailure() {
        ActionPlanEventValidator validator = mock(ActionPlanEventValidator.class);
        Map<String, Object> invalidEvent = Map.of("specversion", "1.0");
        when(validator.validate(invalidEvent)).thenReturn(Optional.empty());
        ActionPlanService service = new ActionPlanService(
                mock(ActionPlanRepository.class),
                mock(SafetyValidator.class),
                mock(AuditService.class),
                mock(ObjectMapper.class),
                mockKafkaTemplate(),
                validator,
                contractSchemaValidator());

        assertThatThrownBy(() -> service.consumeActionPlan(invalidEvent))
                .isInstanceOf(IllegalStateException.class)
                .hasCauseInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void commandFeedbackListenerPropagatesInvalidPayloadFailure() {
        CommandFeedbackConsumer consumer = new CommandFeedbackConsumer(
                mock(ActionPlanRepository.class),
                mock(AuditService.class),
                contractSchemaValidator(),
                120);

        assertThatThrownBy(() -> consumer.onFeedback(Map.of("type", "feedback")))
                .isInstanceOf(IllegalStateException.class)
                .hasCauseInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void insightListenerPersistsValidPayloadAndAuditsDetection() {
        InsightRepository repository = mock(InsightRepository.class);
        InsightEventParser parser = mock(InsightEventParser.class);
        AuditService auditService = mock(AuditService.class);
        Map<String, Object> event = Map.of("farmId", "farm-1", "status", "NORMAL");
        Insight insight = Insight.builder()
                .traceId("trace-uuid-123")
                .farmId("farm-1")
                .status("NORMAL")
                .message("All good")
                .timestamp(Instant.now())
                .build();
        Insight savedInsight = Insight.builder()
                .id(42L)
                .traceId("trace-uuid-123")
                .farmId("farm-1")
                .status("NORMAL")
                .message("All good")
                .timestamp(insight.getTimestamp())
                .build();
        when(parser.parse(event)).thenReturn(Optional.of(insight));
        when(repository.save(insight)).thenReturn(savedInsight);
        KafkaConsumerService consumer = new KafkaConsumerService(
                repository, parser, auditService, contractSchemaValidator());

        consumer.consumeInsight(event);

        verify(repository).save(insight);
        verify(auditService).logInsightDetected(
                "trace-uuid-123", "42", "farm-1", "NORMAL", "All good");
    }

    @Test
    void insightListenerUsesPersistedIdWhenTraceIdIsMissing() {
        InsightRepository repository = mock(InsightRepository.class);
        InsightEventParser parser = mock(InsightEventParser.class);
        AuditService auditService = mock(AuditService.class);
        Map<String, Object> event = Map.of("farmId", "farm-1", "status", "NORMAL");
        Insight insight = Insight.builder()
                .farmId("farm-1")
                .status("NORMAL")
                .message("Legacy insight")
                .timestamp(Instant.now())
                .build();
        Insight savedInsight = Insight.builder()
                .id(42L)
                .farmId("farm-1")
                .status("NORMAL")
                .message("Legacy insight")
                .timestamp(insight.getTimestamp())
                .build();
        when(parser.parse(event)).thenReturn(Optional.of(insight));
        when(repository.save(insight)).thenReturn(savedInsight);
        KafkaConsumerService consumer = new KafkaConsumerService(
                repository, parser, auditService, contractSchemaValidator());

        consumer.consumeInsight(event);

        verify(auditService).logInsightDetected(
                "insight-detected-id-42", "42", "farm-1", "NORMAL", "Legacy insight");
    }

    @SuppressWarnings("unchecked")
    private KafkaTemplate<String, Object> mockKafkaTemplate() {
        return mock(KafkaTemplate.class);
    }

    private ContractSchemaValidator contractSchemaValidator() {
        return new ContractSchemaValidator(new ObjectMapper());
    }
}
