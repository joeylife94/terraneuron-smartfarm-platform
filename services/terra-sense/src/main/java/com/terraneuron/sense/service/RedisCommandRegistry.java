package com.terraneuron.sense.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.SetOperations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/**
 * Redis-backed command correlation and duplicate suppression.
 *
 * Pending command data, a short publish lease, a published marker, and a terminal
 * completion marker are separate keys. This prevents a crash before MQTT publish
 * from being misreported as a successful delivery.
 */
@Slf4j
@Service
public class RedisCommandRegistry implements CommandRegistry {

    static final String PENDING_PREFIX = "terra:sense:command:pending:";
    static final String PUBLISHING_PREFIX = "terra:sense:command:publishing:";
    static final String PUBLISHED_PREFIX = "terra:sense:command:published:";
    static final String COMPLETED_PREFIX = "terra:sense:command:completed:";
    static final String PENDING_INDEX_KEY = "terra:sense:command:pending-index";

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final Duration pendingTtl;
    private final Duration completedTtl;
    private final Duration publishLeaseTtl;

    public RedisCommandRegistry(
            StringRedisTemplate redisTemplate,
            ObjectMapper objectMapper,
            @Value("${app.command.registry.pending-ttl-seconds:86400}") long pendingTtlSeconds,
            @Value("${app.command.registry.completed-ttl-seconds:604800}") long completedTtlSeconds,
            @Value("${app.command.registry.publish-lease-seconds:30}") long publishLeaseSeconds) {
        if (pendingTtlSeconds <= 0 || completedTtlSeconds <= 0 || publishLeaseSeconds <= 0) {
            throw new IllegalArgumentException("Command registry TTLs must be positive");
        }
        this.redisTemplate = redisTemplate;
        this.objectMapper = objectMapper;
        this.pendingTtl = Duration.ofSeconds(pendingTtlSeconds);
        this.completedTtl = Duration.ofSeconds(completedTtlSeconds);
        this.publishLeaseTtl = Duration.ofSeconds(publishLeaseSeconds);
    }

    @Override
    public Registration register(DeviceCommand command) {
        validateCommand(command);
        try {
            String commandId = command.getCommandId();
            ValueOperations<String, String> values = redisTemplate.opsForValue();

            String completedPayload = values.get(completedKey(commandId));
            if (completedPayload != null) {
                assertSameCommand(command, deserializeCompletion(completedPayload).command());
                return new Registration(RegistrationState.COMPLETED);
            }

            String pendingPayload = serialize(command);
            Boolean created = values.setIfAbsent(pendingKey(commandId), pendingPayload, pendingTtl);
            if (Boolean.TRUE.equals(created)) {
                redisTemplate.opsForSet().add(PENDING_INDEX_KEY, commandId);
                log.info("Registered durable pending command: {}", commandId);
            } else {
                String existingPayload = values.get(pendingKey(commandId));
                if (existingPayload != null) {
                    assertSameCommand(command, deserializeCommand(existingPayload));
                } else {
                    completedPayload = values.get(completedKey(commandId));
                    if (completedPayload != null) {
                        assertSameCommand(command, deserializeCompletion(completedPayload).command());
                        return new Registration(RegistrationState.COMPLETED);
                    }
                    throw new IllegalStateException(
                            "Command registry state changed unexpectedly for " + commandId);
                }
            }

            if (Boolean.TRUE.equals(redisTemplate.hasKey(publishedKey(commandId)))) {
                return new Registration(RegistrationState.PUBLISHED);
            }

            Boolean publishLease = values.setIfAbsent(
                    publishingKey(commandId), "1", publishLeaseTtl);
            return new Registration(Boolean.TRUE.equals(publishLease)
                    ? RegistrationState.SHOULD_PUBLISH
                    : RegistrationState.PUBLISH_IN_PROGRESS);
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("Failed to register command in Redis", e);
        }
    }

    @Override
    public void markPublished(String commandId) {
        if (commandId == null || commandId.isBlank()) {
            throw new IllegalArgumentException("commandId is required");
        }
        try {
            // A very fast device ACK may complete while MQTT publish is returning.
            if (Boolean.TRUE.equals(redisTemplate.hasKey(completedKey(commandId)))) {
                redisTemplate.delete(publishingKey(commandId));
                return;
            }
            if (!Boolean.TRUE.equals(redisTemplate.hasKey(pendingKey(commandId)))) {
                throw new IllegalStateException("Cannot mark unknown command as published: " + commandId);
            }
            redisTemplate.opsForValue().set(publishedKey(commandId), "1", pendingTtl);
            redisTemplate.delete(publishingKey(commandId));
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("Failed to mark command as published", e);
        }
    }

    @Override
    public Optional<DeviceCommand> findPending(String commandId) {
        if (commandId == null || commandId.isBlank()) {
            return Optional.empty();
        }
        try {
            String payload = redisTemplate.opsForValue().get(pendingKey(commandId));
            return payload == null ? Optional.empty() : Optional.of(deserializeCommand(payload));
        } catch (Exception e) {
            throw new IllegalStateException("Failed to load pending command from Redis", e);
        }
    }

    @Override
    public boolean claimCompletion(String commandId, String terminalStatus, String error) {
        if (commandId == null || commandId.isBlank()) {
            return false;
        }
        try {
            String pendingPayload = redisTemplate.opsForValue().get(pendingKey(commandId));
            if (pendingPayload == null) {
                return false;
            }

            DeviceCommand command = deserializeCommand(pendingPayload);
            CommandCompletion completion = new CommandCompletion(
                    command,
                    terminalStatus,
                    error,
                    Instant.now());

            return Boolean.TRUE.equals(redisTemplate.opsForValue().setIfAbsent(
                    completedKey(commandId), serialize(completion), completedTtl));
        } catch (Exception e) {
            throw new IllegalStateException("Failed to claim command completion in Redis", e);
        }
    }

    @Override
    public void finishCompletion(String commandId) {
        deletePublicationState(commandId);
    }

    @Override
    public void rollbackCompletion(String commandId) {
        if (commandId == null || commandId.isBlank()) {
            return;
        }
        redisTemplate.delete(completedKey(commandId));
    }

    @Override
    public void releasePending(String commandId) {
        deletePublicationState(commandId);
    }

    @Override
    public long pendingCount() {
        try {
            SetOperations<String, String> sets = redisTemplate.opsForSet();
            Set<String> commandIds = sets.members(PENDING_INDEX_KEY);
            if (commandIds == null || commandIds.isEmpty()) {
                return 0L;
            }

            long active = 0L;
            for (String commandId : commandIds) {
                if (Boolean.TRUE.equals(redisTemplate.hasKey(pendingKey(commandId)))) {
                    active++;
                } else {
                    sets.remove(PENDING_INDEX_KEY, commandId);
                }
            }
            return active;
        } catch (Exception e) {
            log.warn("Unable to calculate pending command count: {}", e.getMessage());
            return -1L;
        }
    }

    private void deletePublicationState(String commandId) {
        if (commandId == null || commandId.isBlank()) {
            return;
        }
        redisTemplate.delete(pendingKey(commandId));
        redisTemplate.delete(publishingKey(commandId));
        redisTemplate.delete(publishedKey(commandId));
        redisTemplate.opsForSet().remove(PENDING_INDEX_KEY, commandId);
    }

    private void validateCommand(DeviceCommand command) {
        if (command == null || command.getCommandId() == null || command.getCommandId().isBlank()) {
            throw new IllegalArgumentException("Device command must contain commandId");
        }
    }

    private void assertSameCommand(DeviceCommand incoming, DeviceCommand stored) {
        boolean same = Objects.equals(incoming.getCommandId(), stored.getCommandId())
                && Objects.equals(incoming.getTraceId(), stored.getTraceId())
                && Objects.equals(incoming.getPlanId(), stored.getPlanId())
                && Objects.equals(incoming.getFarmId(), stored.getFarmId())
                && Objects.equals(incoming.getTargetAssetId(), stored.getTargetAssetId())
                && Objects.equals(incoming.getActionType(), stored.getActionType())
                && Objects.equals(incoming.getParameters(), stored.getParameters())
                && Objects.equals(incoming.getExecutedBy(), stored.getExecutedBy());

        if (!same) {
            throw new IllegalStateException(
                    "Conflicting payload received for existing commandId " + incoming.getCommandId());
        }
    }

    private String serialize(Object value) throws JsonProcessingException {
        return objectMapper.writeValueAsString(value);
    }

    private DeviceCommand deserializeCommand(String payload) throws JsonProcessingException {
        return objectMapper.readValue(payload, DeviceCommand.class);
    }

    private CommandCompletion deserializeCompletion(String payload) throws JsonProcessingException {
        return objectMapper.readValue(payload, CommandCompletion.class);
    }

    private String pendingKey(String commandId) {
        return PENDING_PREFIX + commandId;
    }

    private String publishingKey(String commandId) {
        return PUBLISHING_PREFIX + commandId;
    }

    private String publishedKey(String commandId) {
        return PUBLISHED_PREFIX + commandId;
    }

    private String completedKey(String commandId) {
        return COMPLETED_PREFIX + commandId;
    }
}
