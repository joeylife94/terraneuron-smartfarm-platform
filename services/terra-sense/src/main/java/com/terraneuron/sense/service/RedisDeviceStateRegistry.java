package com.terraneuron.sense.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceStateRecord;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.SetOperations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/** Redis-backed device state shared by every Terra-Sense replica. */
@Slf4j
@Service
public class RedisDeviceStateRegistry implements DeviceStateRegistry {

    static final String STATE_PREFIX = "terra:sense:device-state:";
    static final String INDEX_KEY = "terra:sense:device-state:index";

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final Clock clock;
    private final Duration ttl;
    private final Set<String> quarantinedKeys = ConcurrentHashMap.newKeySet();
    private final AtomicInteger backendAvailable = new AtomicInteger(1);
    private final AtomicLong lastSuccessfulReadEpochMillis = new AtomicLong(0L);

    public RedisDeviceStateRegistry(
            StringRedisTemplate redisTemplate,
            ObjectMapper objectMapper,
            Clock clock,
            MeterRegistry meterRegistry,
            @Value("${app.device-state.registry.ttl-seconds:600}") long ttlSeconds) {
        if (ttlSeconds <= 0) {
            throw new IllegalArgumentException("Device state registry TTL must be positive");
        }
        this.redisTemplate = redisTemplate;
        this.objectMapper = objectMapper;
        this.clock = clock;
        this.ttl = Duration.ofSeconds(ttlSeconds);

        Gauge.builder("terra_device_state_registry_available", backendAvailable, AtomicInteger::get)
                .description("1 when the last shared device-state registry operation succeeded")
                .register(meterRegistry);
        Gauge.builder("terra_device_state_registry_last_success_epoch_seconds",
                        lastSuccessfulReadEpochMillis,
                        value -> value.get() == 0L ? 0D : value.get() / 1000D)
                .description("Epoch time of the last successful shared device-state registry read")
                .register(meterRegistry);
        Gauge.builder("terra_device_state_registry_ttl_seconds", ttl, Duration::toSeconds)
                .description("Configured Redis TTL for device state records")
                .register(meterRegistry);
    }

    @Override
    public void save(DeviceStateRecord state) {
        validateIdentity(state);
        if (state.getObservedAt() == null) {
            state.setObservedAt(clock.instant());
        }

        String stateKey = key(state.getFarmId(), state.getAssetId());
        // Quarantine before the shared write. A concurrent local safety read must not
        // authorize from the previous Redis value while a newer status is being stored.
        quarantinedKeys.add(stateKey);
        try {
            redisTemplate.opsForValue().set(
                    stateKey, objectMapper.writeValueAsString(state), ttl);
            redisTemplate.opsForSet().add(INDEX_KEY, stateKey);
            redisTemplate.expire(INDEX_KEY, ttl.multipliedBy(2));
            quarantinedKeys.remove(stateKey);
            markSuccess();
        } catch (Exception ex) {
            // Keep the local quarantine until a later successful save. The MQTT
            // ingestion path also calls invalidate to remove the superseded shared
            // record for other replicas when Redis permits the cleanup operation.
            markFailure();
            throw unavailable("Failed to store device state in Redis", ex);
        }
    }

    @Override
    public void invalidate(String farmId, String assetId) {
        if (isBlank(farmId) || isBlank(assetId)) {
            return;
        }

        String stateKey = key(farmId, assetId);
        quarantinedKeys.add(stateKey);
        try {
            redisTemplate.delete(stateKey);
            redisTemplate.opsForSet().remove(INDEX_KEY, stateKey);
            markSuccess();
        } catch (Exception ex) {
            // Local reads remain quarantined even when the best-effort shared cleanup
            // cannot complete. A later successful save is the only operation that
            // restores authority for this identity on this replica.
            markFailure();
            throw unavailable("Failed to invalidate device state in Redis", ex);
        }
    }

    @Override
    public Optional<DeviceStateRecord> find(String farmId, String assetId) {
        if (isBlank(farmId) || isBlank(assetId)) {
            return Optional.empty();
        }

        String stateKey = key(farmId, assetId);
        if (quarantinedKeys.contains(stateKey)) {
            return Optional.empty();
        }

        try {
            String payload = redisTemplate.opsForValue().get(stateKey);
            markSuccess();
            if (payload == null) {
                return Optional.empty();
            }
            return Optional.of(objectMapper.readValue(payload, DeviceStateRecord.class));
        } catch (Exception ex) {
            markFailure();
            throw unavailable("Failed to read device state from Redis", ex);
        }
    }

    @Override
    public Map<String, DeviceStateRecord> findAll() {
        try {
            SetOperations<String, String> sets = redisTemplate.opsForSet();
            Set<String> keys = sets.members(INDEX_KEY);
            if (keys == null || keys.isEmpty()) {
                markSuccess();
                return Map.of();
            }

            Map<String, DeviceStateRecord> states = new LinkedHashMap<>();
            for (String stateKey : keys) {
                if (quarantinedKeys.contains(stateKey)) {
                    continue;
                }
                String payload = redisTemplate.opsForValue().get(stateKey);
                if (payload == null) {
                    sets.remove(INDEX_KEY, stateKey);
                    continue;
                }
                DeviceStateRecord state = objectMapper.readValue(payload, DeviceStateRecord.class);
                states.put(state.getFarmId() + "/" + state.getAssetId(), state);
            }
            markSuccess();
            return Map.copyOf(states);
        } catch (Exception ex) {
            markFailure();
            throw unavailable("Failed to enumerate device states from Redis", ex);
        }
    }

    @Override
    public RegistryStatus status() {
        try {
            long tracked = findAll().size();
            return new RegistryStatus("redis", true, lastSuccessfulReadAt(), tracked);
        } catch (DeviceStateRegistryUnavailableException ex) {
            return new RegistryStatus("redis", false, lastSuccessfulReadAt(), -1L);
        }
    }

    private void validateIdentity(DeviceStateRecord state) {
        if (state == null || isBlank(state.getFarmId()) || isBlank(state.getAssetId())) {
            throw new IllegalArgumentException("Device state requires farmId and assetId");
        }
    }

    private String key(String farmId, String assetId) {
        return STATE_PREFIX + encode(farmId) + ":" + encode(assetId);
    }

    private String encode(String value) {
        return Base64.getUrlEncoder().withoutPadding()
                .encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }

    private void markSuccess() {
        backendAvailable.set(1);
        lastSuccessfulReadEpochMillis.set(clock.millis());
    }

    private void markFailure() {
        backendAvailable.set(0);
    }

    private Instant lastSuccessfulReadAt() {
        long value = lastSuccessfulReadEpochMillis.get();
        return value == 0L ? null : Instant.ofEpochMilli(value);
    }

    private DeviceStateRegistryUnavailableException unavailable(String message, Exception ex) {
        log.warn("{}: {}", message, ex.getClass().getSimpleName());
        return new DeviceStateRegistryUnavailableException(message, ex);
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
