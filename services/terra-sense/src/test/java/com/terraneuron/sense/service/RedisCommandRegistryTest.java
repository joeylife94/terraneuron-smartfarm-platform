package com.terraneuron.sense.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.SetOperations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RedisCommandRegistryTest {

    private static final String COMMAND_ID = "cmd-1a2b3c4d";
    private static final String PENDING_KEY = RedisCommandRegistry.PENDING_PREFIX + COMMAND_ID;
    private static final String PUBLISHING_KEY = RedisCommandRegistry.PUBLISHING_PREFIX + COMMAND_ID;
    private static final String PUBLISHED_KEY = RedisCommandRegistry.PUBLISHED_PREFIX + COMMAND_ID;
    private static final String COMPLETED_KEY = RedisCommandRegistry.COMPLETED_PREFIX + COMMAND_ID;

    @Mock
    private StringRedisTemplate redisTemplate;
    @Mock
    private ValueOperations<String, String> values;
    @Mock
    private SetOperations<String, String> sets;

    private ObjectMapper objectMapper;
    private RedisCommandRegistry registry;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper().findAndRegisterModules();
        when(redisTemplate.opsForValue()).thenReturn(values);
        when(redisTemplate.opsForSet()).thenReturn(sets);
        registry = new RedisCommandRegistry(redisTemplate, objectMapper, 3600, 7200, 30);
    }

    @Test
    void firstRegistrationCreatesPendingRecordAndPublishLease() {
        when(values.get(COMPLETED_KEY)).thenReturn(null);
        when(values.setIfAbsent(eq(PENDING_KEY), anyString(), eq(Duration.ofSeconds(3600))))
                .thenReturn(true);
        when(redisTemplate.hasKey(PUBLISHED_KEY)).thenReturn(false);
        when(values.setIfAbsent(PUBLISHING_KEY, "1", Duration.ofSeconds(30)))
                .thenReturn(true);

        CommandRegistry.Registration registration = registry.register(command("fan-01"));

        assertThat(registration.state())
                .isEqualTo(CommandRegistry.RegistrationState.SHOULD_PUBLISH);
        verify(sets).add(RedisCommandRegistry.PENDING_INDEX_KEY, COMMAND_ID);
    }

    @Test
    void durablyPublishedCommandDoesNotAcquireAnotherPublishLease() throws Exception {
        DeviceCommand command = command("fan-01");
        when(values.get(COMPLETED_KEY)).thenReturn(null);
        when(values.setIfAbsent(eq(PENDING_KEY), anyString(), eq(Duration.ofSeconds(3600))))
                .thenReturn(false);
        when(values.get(PENDING_KEY)).thenReturn(objectMapper.writeValueAsString(command));
        when(redisTemplate.hasKey(PUBLISHED_KEY)).thenReturn(true);

        CommandRegistry.Registration registration = registry.register(command("fan-01"));

        assertThat(registration.state())
                .isEqualTo(CommandRegistry.RegistrationState.PUBLISHED);
    }

    @Test
    void activePublishLeasePreventsFalseDeliveredState() throws Exception {
        DeviceCommand command = command("fan-01");
        when(values.get(COMPLETED_KEY)).thenReturn(null);
        when(values.setIfAbsent(eq(PENDING_KEY), anyString(), eq(Duration.ofSeconds(3600))))
                .thenReturn(false);
        when(values.get(PENDING_KEY)).thenReturn(objectMapper.writeValueAsString(command));
        when(redisTemplate.hasKey(PUBLISHED_KEY)).thenReturn(false);
        when(values.setIfAbsent(PUBLISHING_KEY, "1", Duration.ofSeconds(30)))
                .thenReturn(false);

        CommandRegistry.Registration registration = registry.register(command("fan-01"));

        assertThat(registration.state())
                .isEqualTo(CommandRegistry.RegistrationState.PUBLISH_IN_PROGRESS);
    }

    @Test
    void conflictingPayloadForExistingCommandIdIsRejected() throws Exception {
        when(values.get(COMPLETED_KEY)).thenReturn(null);
        when(values.setIfAbsent(eq(PENDING_KEY), anyString(), eq(Duration.ofSeconds(3600))))
                .thenReturn(false);
        when(values.get(PENDING_KEY))
                .thenReturn(objectMapper.writeValueAsString(command("fan-01")));

        assertThatThrownBy(() -> registry.register(command("heater-01")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Conflicting payload")
                .hasMessageContaining(COMMAND_ID);
    }

    @Test
    void completedCommandRemainsSuppressedAcrossConsumerRestarts() throws Exception {
        CommandRegistry.CommandCompletion completion = new CommandRegistry.CommandCompletion(
                command("fan-01"), "EXECUTED", "", Instant.now());
        when(values.get(COMPLETED_KEY))
                .thenReturn(objectMapper.writeValueAsString(completion));

        CommandRegistry.Registration registration = registry.register(command("fan-01"));

        assertThat(registration.state()).isEqualTo(CommandRegistry.RegistrationState.COMPLETED);
    }

    @Test
    void successfulMqttPublishCreatesDurablePublishedMarker() {
        when(redisTemplate.hasKey(COMPLETED_KEY)).thenReturn(false);
        when(redisTemplate.hasKey(PENDING_KEY)).thenReturn(true);

        registry.markPublished(COMMAND_ID);

        verify(values).set(PUBLISHED_KEY, "1", Duration.ofSeconds(3600));
        verify(redisTemplate).delete(PUBLISHING_KEY);
    }

    @Test
    void terminalAckIsClaimedOnceAndPublicationStateRemovedAfterKafkaAck() throws Exception {
        when(values.get(PENDING_KEY))
                .thenReturn(objectMapper.writeValueAsString(command("fan-01")));
        when(values.setIfAbsent(eq(COMPLETED_KEY), anyString(), eq(Duration.ofSeconds(7200))))
                .thenReturn(true);

        assertThat(registry.claimCompletion(COMMAND_ID, "EXECUTED", "")).isTrue();

        registry.finishCompletion(COMMAND_ID);
        verify(redisTemplate).delete(PENDING_KEY);
        verify(redisTemplate).delete(PUBLISHING_KEY);
        verify(redisTemplate).delete(PUBLISHED_KEY);
        verify(sets).remove(RedisCommandRegistry.PENDING_INDEX_KEY, COMMAND_ID);
    }

    @Test
    void failedKafkaFeedbackCanReleaseCompletionClaimForRetry() {
        registry.rollbackCompletion(COMMAND_ID);

        verify(redisTemplate).delete(COMPLETED_KEY);
    }

    private DeviceCommand command(String assetId) {
        return DeviceCommand.builder()
                .commandId(COMMAND_ID)
                .traceId("trace-123")
                .planId("plan-123")
                .farmId("farm-001")
                .targetAssetId(assetId)
                .actionType("turn_on")
                .parameters(Map.of("duration_minutes", 30))
                .executedBy("operator-01")
                .issuedAt(Instant.parse("2026-07-15T11:59:00Z"))
                .build();
    }
}
