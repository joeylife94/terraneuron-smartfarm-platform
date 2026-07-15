package com.terraneuron.ops.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.CommandOutboxEvent;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/** Polls the transactional outbox and publishes commands to Kafka at least once. */
@Slf4j
@Service
public class CommandOutboxPublisher {

    private final CommandOutboxStateService stateService;
    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final ObjectMapper objectMapper;
    private final Duration lockTimeout;
    private final Duration baseBackoff;
    private final int maxAttempts;
    private final long kafkaAckTimeoutSeconds;

    public CommandOutboxPublisher(
            CommandOutboxStateService stateService,
            KafkaTemplate<String, Object> kafkaTemplate,
            ObjectMapper objectMapper,
            @Value("${app.command.outbox.lock-timeout-seconds:60}") long lockTimeoutSeconds,
            @Value("${app.command.outbox.base-backoff-seconds:2}") long baseBackoffSeconds,
            @Value("${app.command.outbox.max-attempts:8}") int maxAttempts,
            @Value("${app.command.outbox.kafka-ack-timeout-seconds:10}") long kafkaAckTimeoutSeconds) {
        if (lockTimeoutSeconds <= 0 || baseBackoffSeconds <= 0
                || maxAttempts <= 0 || kafkaAckTimeoutSeconds <= 0) {
            throw new IllegalArgumentException("Command outbox settings must be positive");
        }
        this.stateService = stateService;
        this.kafkaTemplate = kafkaTemplate;
        this.objectMapper = objectMapper;
        this.lockTimeout = Duration.ofSeconds(lockTimeoutSeconds);
        this.baseBackoff = Duration.ofSeconds(baseBackoffSeconds);
        this.maxAttempts = maxAttempts;
        this.kafkaAckTimeoutSeconds = kafkaAckTimeoutSeconds;
    }

    @Scheduled(fixedDelayString = "${app.command.outbox.poll-ms:1000}")
    public void publishPendingCommands() {
        Instant now = Instant.now();
        int recovered = stateService.recoverStaleClaims(now, lockTimeout);
        if (recovered > 0) {
            log.warn("Recovered {} stale command outbox claims", recovered);
        }

        for (CommandOutboxEvent candidate : stateService.findReady(now)) {
            if (!stateService.claim(candidate.getId(), Instant.now())) {
                continue;
            }
            publishClaimed(candidate.getId());
        }
    }

    private void publishClaimed(Long eventId) {
        try {
            CommandOutboxEvent event = stateService.getRequired(eventId);
            Map<String, Object> payload = objectMapper.readValue(
                    event.getPayload(),
                    new TypeReference<Map<String, Object>>() { });

            kafkaTemplate.send(event.getTopic(), event.getMessageKey(), payload)
                    .get(kafkaAckTimeoutSeconds, TimeUnit.SECONDS);

            stateService.markPublished(eventId, Instant.now());
            log.info("Command outbox published: event={} command={}",
                    event.getEventId(), event.getCommandId());
        } catch (Exception e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            String error = rootCauseMessage(e);
            log.error("Command outbox publication failed: event={} error={}",
                    eventId, error, e);
            try {
                stateService.markFailed(
                        eventId,
                        error,
                        Instant.now(),
                        maxAttempts,
                        baseBackoff);
            } catch (Exception stateError) {
                log.error("Failed to persist outbox failure state: event={} error={}",
                        eventId, stateError.getMessage(), stateError);
            }
        }
    }

    private String rootCauseMessage(Exception exception) {
        Throwable cause = exception;
        while (cause.getCause() != null) {
            cause = cause.getCause();
        }
        return cause.getMessage() != null
                ? cause.getMessage()
                : cause.getClass().getSimpleName();
    }
}
