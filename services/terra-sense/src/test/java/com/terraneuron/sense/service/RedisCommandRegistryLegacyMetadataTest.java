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
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RedisCommandRegistryLegacyMetadataTest {

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
        lenient().when(redisTemplate.opsForValue()).thenReturn(values);
        lenient().when(redisTemplate.opsForSet()).thenReturn(sets);
        registry = new RedisCommandRegistry(redisTemplate, objectMapper, 3600, 7200, 30);
    }

    @Test
    void modernRedeliveryAcceptsLegacyPendingMetadata() throws Exception {
        DeviceCommand legacyStored = command(null, null);
        DeviceCommand modernIncoming = command("device", "ventilation");

        when(values.get(COMPLETED_KEY)).thenReturn(null);
        when(values.setIfAbsent(eq(PENDING_KEY), anyString(), eq(Duration.ofSeconds(3600))))
                .thenReturn(false);
        when(values.get(PENDING_KEY))
                .thenReturn(objectMapper.writeValueAsString(legacyStored));
        when(redisTemplate.hasKey(PUBLISHED_KEY)).thenReturn(true);

        CommandRegistry.Registration registration = registry.register(modernIncoming);

        assertThat(registration.state()).isEqualTo(CommandRegistry.RegistrationState.PUBLISHED);
    }

    @Test
    void modernRedeliveryAcceptsLegacyCompletionMetadata() throws Exception {
        DeviceCommand legacyStored = command(null, null);
        CommandRegistry.CommandCompletion completion = new CommandRegistry.CommandCompletion(
                legacyStored,
                "FAILED",
                "DEVICE_SAFETY_BLOCKED:STATE_OFFLINE",
                Instant.parse("2026-07-18T03:00:01Z"));
        when(values.get(COMPLETED_KEY))
                .thenReturn(objectMapper.writeValueAsString(completion));

        CommandRegistry.Registration registration = registry.register(
                command("device", "ventilation"));

        assertThat(registration.state()).isEqualTo(CommandRegistry.RegistrationState.COMPLETED);
    }

    @Test
    void legacyRedeliveryAcceptsModernStoredMetadata() throws Exception {
        DeviceCommand modernStored = command("device", "ventilation");

        when(values.get(COMPLETED_KEY)).thenReturn(null);
        when(values.setIfAbsent(eq(PENDING_KEY), anyString(), eq(Duration.ofSeconds(3600))))
                .thenReturn(false);
        when(values.get(PENDING_KEY))
                .thenReturn(objectMapper.writeValueAsString(modernStored));
        when(redisTemplate.hasKey(PUBLISHED_KEY)).thenReturn(false);
        when(values.setIfAbsent(PUBLISHING_KEY, "1", Duration.ofSeconds(30)))
                .thenReturn(false);

        CommandRegistry.Registration registration = registry.register(command(null, null));

        assertThat(registration.state())
                .isEqualTo(CommandRegistry.RegistrationState.PUBLISH_IN_PROGRESS);
    }

    @Test
    void populatedMetadataStillMustMatchExactly() throws Exception {
        DeviceCommand stored = command("device", "ventilation");

        when(values.get(COMPLETED_KEY)).thenReturn(null);
        when(values.setIfAbsent(eq(PENDING_KEY), anyString(), eq(Duration.ofSeconds(3600))))
                .thenReturn(false);
        when(values.get(PENDING_KEY)).thenReturn(objectMapper.writeValueAsString(stored));

        assertThatThrownBy(() -> registry.register(command("device", "heating")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Conflicting payload")
                .hasMessageContaining(COMMAND_ID);
    }

    private DeviceCommand command(String targetAssetType, String actionCategory) {
        return DeviceCommand.builder()
                .commandId(COMMAND_ID)
                .traceId("trace-123")
                .planId("plan-123")
                .farmId("farm-001")
                .targetAssetId("fan-01")
                .targetAssetType(targetAssetType)
                .actionCategory(actionCategory)
                .actionType("turn_on")
                .parameters(Map.of("duration_minutes", 30))
                .executedBy("operator-01")
                .issuedAt(Instant.parse("2026-07-15T11:59:00Z"))
                .build();
    }
}
