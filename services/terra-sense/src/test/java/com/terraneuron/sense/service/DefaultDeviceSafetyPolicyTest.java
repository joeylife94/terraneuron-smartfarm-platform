package com.terraneuron.sense.service;

import com.terraneuron.sense.model.DeviceSafetyDecision;
import com.terraneuron.sense.model.DeviceSafetyReason;
import com.terraneuron.sense.model.DeviceSafetyRequest;
import com.terraneuron.sense.model.DeviceStateRecord;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DefaultDeviceSafetyPolicyTest {

    private static final Instant NOW = Instant.parse("2026-07-18T03:00:00Z");

    private FakeRegistry registry;
    private DefaultDeviceSafetyPolicy policy;

    @BeforeEach
    void setUp() {
        registry = new FakeRegistry();
        policy = new DefaultDeviceSafetyPolicy(
                registry,
                java.util.List.of(new DefaultDeviceCapabilityResolver()),
                new SimpleMeterRegistry(),
                Clock.fixed(NOW, ZoneOffset.UTC),
                120,
                600,
                10);
    }

    @Test
    void freshOnlineCompatibleDeviceIsAllowed() {
        registry.save(state("online", false, "fan", NOW.minusSeconds(30), NOW.minusSeconds(5)));
        assertThat(evaluate("ventilation", "turn_on", Map.of()).allowed()).isTrue();
    }

    @Test
    void missingStateIsBlocked() {
        assertReason(evaluate("ventilation", "turn_on", Map.of()), DeviceSafetyReason.STATE_MISSING);
    }

    @Test
    void staleObservedStateIsBlocked() {
        registry.save(state("online", false, "fan", NOW.minusSeconds(121), NOW.minusSeconds(5)));
        assertReason(evaluate("ventilation", "turn_on", Map.of()), DeviceSafetyReason.STATE_STALE);
    }

    @Test
    void staleDeviceReportedStateIsBlocked() {
        registry.save(state("online", false, "fan", NOW.minusSeconds(5), NOW.minusSeconds(121)));
        assertReason(evaluate("ventilation", "turn_on", Map.of()), DeviceSafetyReason.REPORTED_STATE_STALE);
    }

    @Test
    void offlineErrorAndUnknownStatesAreBlocked() {
        registry.save(state("offline", false, "fan", NOW, NOW));
        assertReason(evaluate("ventilation", "turn_on", Map.of()), DeviceSafetyReason.STATE_OFFLINE);
        registry.save(state("error", false, "fan", NOW, NOW));
        assertReason(evaluate("ventilation", "turn_on", Map.of()), DeviceSafetyReason.STATE_ERROR);
        registry.save(state("unknown", false, "fan", NOW, NOW));
        assertReason(evaluate("ventilation", "turn_on", Map.of()), DeviceSafetyReason.STATE_UNKNOWN);
    }

    @Test
    void maintenanceModeIsBlocked() {
        registry.save(state("idle", true, "fan", NOW, NOW));
        assertReason(evaluate("ventilation", "turn_on", Map.of()), DeviceSafetyReason.MAINTENANCE_MODE);
    }

    @Test
    void deviceTypeAndActionCompatibilityAreExplicit() {
        registry.save(state("online", false, "heater", NOW, NOW));
        assertReason(evaluate("ventilation", "turn_on", Map.of()),
                DeviceSafetyReason.ACTION_CATEGORY_MISMATCH);
        assertReason(evaluate("heating", "calibrate", Map.of()),
                DeviceSafetyReason.ACTION_UNSUPPORTED);
    }

    @Test
    void unsupportedDeviceTypeFailsClosed() {
        registry.save(state("online", false, "vendor-model-x", NOW, NOW));
        assertReason(evaluate("ventilation", "turn_on", Map.of()),
                DeviceSafetyReason.UNSUPPORTED_DEVICE_TYPE);
    }

    @Test
    void adjustRequiresAtLeastOneSupportedParameter() {
        registry.save(state("running", false, "fan", NOW, NOW));
        assertReason(evaluate("ventilation", "adjust", Map.of("unsupported", 1)),
                DeviceSafetyReason.ADJUST_PARAMETERS_MISSING);
        assertThat(evaluate("ventilation", "adjust", Map.of("speed_level", "high")).allowed())
                .isTrue();
    }

    @Test
    void registryFailureFailsClosed() {
        registry.unavailable = true;
        assertReason(evaluate("ventilation", "turn_on", Map.of()),
                DeviceSafetyReason.REGISTRY_UNAVAILABLE);
    }

    @Test
    void mismatchedStoredIdentityIsBlocked() {
        DeviceStateRecord state = state("online", false, "fan", NOW, NOW);
        state.setFarmId("other-farm");
        registry.forced = state;
        assertReason(evaluate("ventilation", "turn_on", Map.of()),
                DeviceSafetyReason.IDENTITY_MISMATCH);
    }

    @Test
    void registryTtlMustRemainGreaterThanFreshness() {
        assertThatThrownBy(() -> new DefaultDeviceSafetyPolicy(
                registry,
                java.util.List.of(new DefaultDeviceCapabilityResolver()),
                new SimpleMeterRegistry(),
                Clock.fixed(NOW, ZoneOffset.UTC),
                120,
                120,
                10))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("greater than the freshness");
    }

    private DeviceSafetyDecision evaluate(
            String category,
            String action,
            Map<String, Object> parameters) {
        return policy.evaluate(new DeviceSafetyRequest(
                "farm-1", "fan-01", category, action, parameters));
    }

    private DeviceStateRecord state(
            String state,
            boolean maintenance,
            String type,
            Instant observedAt,
            Instant reportedAt) {
        return DeviceStateRecord.builder()
                .farmId("farm-1")
                .assetId("fan-01")
                .deviceType(type)
                .state(state)
                .maintenanceMode(maintenance)
                .observedAt(observedAt)
                .reportedAt(reportedAt)
                .build();
    }

    private void assertReason(DeviceSafetyDecision decision, DeviceSafetyReason reason) {
        assertThat(decision.allowed()).isFalse();
        assertThat(decision.reasonCode()).isEqualTo(reason);
    }

    private static class FakeRegistry implements DeviceStateRegistry {
        private final Map<String, DeviceStateRecord> states = new LinkedHashMap<>();
        private boolean unavailable;
        private DeviceStateRecord forced;

        @Override
        public void save(DeviceStateRecord state) {
            states.put(state.getFarmId() + "/" + state.getAssetId(), state);
        }

        @Override
        public Optional<DeviceStateRecord> find(String farmId, String assetId) {
            if (unavailable) {
                throw new DeviceStateRegistryUnavailableException("unavailable", new RuntimeException());
            }
            if (forced != null) return Optional.of(forced);
            return Optional.ofNullable(states.get(farmId + "/" + assetId));
        }

        @Override
        public Map<String, DeviceStateRecord> findAll() {
            return Map.copyOf(states);
        }

        @Override
        public RegistryStatus status() {
            return new RegistryStatus("fake", !unavailable, NOW, states.size());
        }
    }
}
