package com.terraneuron.ops.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.CommandOutboxEvent;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.CompletableFuture;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CommandOutboxPublisherTest {

    @Mock
    private CommandOutboxStateService stateService;
    @Mock
    private KafkaTemplate<String, Object> kafkaTemplate;

    private CommandOutboxPublisher publisher;

    @BeforeEach
    void setUp() {
        publisher = new CommandOutboxPublisher(
                stateService,
                kafkaTemplate,
                new ObjectMapper(),
                60,
                2,
                3,
                10);
    }

    @Test
    void brokerAcknowledgementMarksClaimedEventPublished() {
        CommandOutboxEvent event = event();
        when(stateService.recoverStaleClaims(any(Instant.class), eq(Duration.ofSeconds(60))))
                .thenReturn(0);
        when(stateService.findReady(any(Instant.class))).thenReturn(List.of(event));
        when(stateService.claim(eq(1L), any(Instant.class))).thenReturn(true);
        when(stateService.getRequired(1L)).thenReturn(event);
        CompletableFuture<SendResult<String, Object>> future =
                CompletableFuture.completedFuture(null);
        when(kafkaTemplate.send(eq("terra.control.command"), eq("farm-1"), any()))
                .thenReturn(future);

        publisher.publishPendingCommands();

        verify(stateService).markPublished(eq(1L), any(Instant.class));
    }

    @Test
    void brokerFailurePersistsRetryStateInsteadOfLosingCommand() {
        CommandOutboxEvent event = event();
        when(stateService.recoverStaleClaims(any(Instant.class), eq(Duration.ofSeconds(60))))
                .thenReturn(0);
        when(stateService.findReady(any(Instant.class))).thenReturn(List.of(event));
        when(stateService.claim(eq(1L), any(Instant.class))).thenReturn(true);
        when(stateService.getRequired(1L)).thenReturn(event);
        CompletableFuture<SendResult<String, Object>> future = new CompletableFuture<>();
        future.completeExceptionally(new RuntimeException("broker unavailable"));
        when(kafkaTemplate.send(eq("terra.control.command"), eq("farm-1"), any()))
                .thenReturn(future);

        publisher.publishPendingCommands();

        verify(stateService).markFailed(
                eq(1L),
                eq("broker unavailable"),
                any(Instant.class),
                eq(3),
                eq(Duration.ofSeconds(2)));
    }

    private CommandOutboxEvent event() {
        return CommandOutboxEvent.builder()
                .id(1L)
                .eventId("event-1")
                .planId("plan-1")
                .commandId("cmd-1")
                .topic("terra.control.command")
                .messageKey("farm-1")
                .payload("{\"type\":\"terra.ops.command.execute\",\"data\":{}}")
                .status(CommandOutboxEvent.OutboxStatus.PENDING)
                .attempts(0)
                .nextAttemptAt(Instant.now())
                .build();
    }
}
