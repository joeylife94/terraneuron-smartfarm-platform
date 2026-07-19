package com.terraneuron.sense.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceStateRecord;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.SetOperations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RedisDeviceStateRegistryTest {

    @Mock private StringRedisTemplate redisTemplate;
    @Mock private ValueOperations<String, String> values;
    @Mock private SetOperations<String, String> sets;

    private ObjectMapper objectMapper;
    private RedisDeviceStateRegistry registry;
    private Clock clock;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper().findAndRegisterModules();
        clock = Clock.fixed(Instant.parse("2026-07-18T03:00:00Z"), ZoneOffset.UTC);
        lenient().when(redisTemplate.opsForValue()).thenReturn(values);
        lenient().when(redisTemplate.opsForSet()).thenReturn(sets);
        registry = new RedisDeviceStateRegistry(
                redisTemplate, objectMapper, clock, new SimpleMeterRegistry(), 600);
    }

    @Test
    void validStateIsStoredLongerThanDefaultFreshness() {
        DeviceStateRecord state = state();

        registry.save(state);

        verify(values).set(anyString(), anyString(), eq(Duration.ofSeconds(600)));
        assertThat(Duration.ofSeconds(600)).isGreaterThan(Duration.ofSeconds(120));
    }

    @Test
    void anotherReplicaReadsTheSameRedisRecord() throws Exception {
        DeviceStateRecord state = state();
        when(values.get(anyString())).thenReturn(objectMapper.writeValueAsString(state));
        RedisDeviceStateRegistry secondReplica = new RedisDeviceStateRegistry(
                redisTemplate, objectMapper, clock, new SimpleMeterRegistry(), 600);

        DeviceStateRecord loaded = secondReplica.find("farm-1", "fan-01").orElseThrow();

        assertThat(loaded.getFarmId()).isEqualTo("farm-1");
        assertThat(loaded.getAssetId()).isEqualTo("fan-01");
        assertThat(loaded.getObservedAt()).isEqualTo(state.getObservedAt());
    }

    @Test
    void failedSaveQuarantinesOldRecordUntilACompleteSaveSucceeds() throws Exception {
        DeviceStateRecord state = state();
        doThrow(new RuntimeException("write rejected"))
                .doNothing()
                .when(values)
                .set(anyString(), anyString(), eq(Duration.ofSeconds(600)));
        when(values.get(anyString())).thenReturn(objectMapper.writeValueAsString(state));

        assertThatThrownBy(() -> registry.save(state))
                .isInstanceOf(DeviceStateRegistryUnavailableException.class);
        assertThat(registry.find("farm-1", "fan-01")).isEmpty();

        registry.save(state);

        assertThat(registry.find("farm-1", "fan-01")).isPresent();
    }

    @Test
    void invalidationRemovesSharedRecordAndKeepsLocalReadsFailClosed() {
        registry.invalidate("farm-1", "fan-01");

        verify(redisTemplate).delete(anyString());
        verify(sets).remove(eq(RedisDeviceStateRegistry.INDEX_KEY), anyString());
        assertThat(registry.find("farm-1", "fan-01")).isEmpty();
    }

    @Test
    void redisFailureIsExplicitForFailClosedCallers() {
        when(values.get(anyString())).thenThrow(new RuntimeException("redis down"));

        assertThatThrownBy(() -> registry.find("farm-1", "fan-01"))
                .isInstanceOf(DeviceStateRegistryUnavailableException.class);
    }

    private DeviceStateRecord state() {
        return DeviceStateRecord.builder()
                .farmId("farm-1")
                .assetId("fan-01")
                .deviceType("fan")
                .state("online")
                .reportedAt(clock.instant())
                .observedAt(clock.instant())
                .build();
    }
}
