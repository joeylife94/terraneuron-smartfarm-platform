package com.terraneuron.sense.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.SetOperations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RedisCommandCompletionReplayTest {

    @Mock private StringRedisTemplate redisTemplate;
    @Mock private ValueOperations<String, String> values;
    @Mock private SetOperations<String, String> sets;

    @Test
    void durableCompletionCanBeLoadedAfterPublicationStateCleanup() throws Exception {
        ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();
        RedisCommandRegistry registry = new RedisCommandRegistry(
                redisTemplate, objectMapper, 3600, 7200, 30);
        DeviceCommand command = DeviceCommand.builder()
                .commandId("cmd-1a2b3c4d")
                .traceId("trace-123")
                .planId("plan-123")
                .farmId("farm-001")
                .targetAssetId("fan-01")
                .actionType("turn_on")
                .parameters(Map.of("duration_minutes", 30))
                .executedBy("operator-01")
                .issuedAt(Instant.parse("2026-07-18T03:00:00Z"))
                .build();
        CommandRegistry.CommandCompletion completion = new CommandRegistry.CommandCompletion(
                command,
                "FAILED",
                "DEVICE_SAFETY_BLOCKED:STATE_OFFLINE",
                Instant.parse("2026-07-18T03:00:01Z"));

        when(redisTemplate.opsForValue()).thenReturn(values);
        when(redisTemplate.opsForSet()).thenReturn(sets);
        when(values.get(RedisCommandRegistry.COMPLETED_PREFIX + command.getCommandId()))
                .thenReturn(objectMapper.writeValueAsString(completion));

        CommandRegistry.CommandCompletion loaded = registry
                .findCompletion(command.getCommandId())
                .orElseThrow();

        assertThat(loaded.command().getCommandId()).isEqualTo(command.getCommandId());
        assertThat(loaded.terminalStatus()).isEqualTo("FAILED");
        assertThat(loaded.error()).isEqualTo("DEVICE_SAFETY_BLOCKED:STATE_OFFLINE");
    }
}
