package com.terraneuron.sense.service;

import com.terraneuron.sense.model.DeviceSafetyDecision;
import com.terraneuron.sense.model.DeviceSafetyReason;
import com.terraneuron.sense.model.DeviceSafetyRequest;
import com.terraneuron.sense.model.DeviceStateRecord;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class SyntheticConformanceDeviceCapabilityResolverTest {

    private static final Instant NOW = Instant.parse("2026-09-11T12:00:00Z");
    private final SyntheticConformanceDeviceCapabilityResolver resolver =
            new SyntheticConformanceDeviceCapabilityResolver();

    @Test
    void knownSyntheticModelDeclaresOnlyBoundedCapabilities() {
        DeviceCapabilityResolver.DeviceCapabilities capabilities = resolver.resolve(state(
                SyntheticConformanceDeviceCapabilityResolver.MODEL_ID)).orElseThrow();

        assertThat(capabilities.actionCategories()).containsExactly("heating");
        assertThat(capabilities.actionTypes()).containsExactlyInAnyOrder("turn_on", "turn_off", "adjust");
        assertThat(capabilities.adjustParameterAnyOf()).containsExactly("target_temperature");
    }

    @Test
    void unrelatedStateFallsThroughButUnknownSyntheticModelIsClaimedFailClosed() {
        DeviceStateRecord unrelated = DeviceStateRecord.builder()
                .farmId("farm-d4")
                .assetId("device-a")
                .deviceType("heater")
                .state("online")
                .reportedAt(NOW)
                .observedAt(NOW)
                .attributes(Map.of())
                .build();

        assertThat(resolver.resolve(unrelated)).isEmpty();
        DeviceCapabilityResolver.DeviceCapabilities unknown = resolver.resolve(state("tn-synth-unknown"))
                .orElseThrow();
        assertThat(unknown.actionCategories()).isEmpty();
        assertThat(unknown.actionTypes()).isEmpty();
    }

    @Test
    void safetyPolicyAdmitsDeclaredActionAndRejectsUnsupportedOrUnknownModel() {
        FakeRegistry registry = new FakeRegistry();
        DefaultDeviceSafetyPolicy policy = new DefaultDeviceSafetyPolicy(
                registry,
                List.of(resolver, new DefaultDeviceCapabilityResolver()),
                new SimpleMeterRegistry(),
                Clock.fixed(NOW, ZoneOffset.UTC),
                120,
                600,
                10);

        registry.save(state(SyntheticConformanceDeviceCapabilityResolver.MODEL_ID));
        DeviceSafetyDecision allowed = policy.evaluate(request("heating", "turn_on", Map.of()));
        assertThat(allowed.allowed()).isTrue();

        DeviceSafetyDecision unsupported = policy.evaluate(request("heating", "alert_only", Map.of()));
        assertThat(unsupported.allowed()).isFalse();
        assertThat(unsupported.reasonCode()).isEqualTo(DeviceSafetyReason.ACTION_UNSUPPORTED);

        registry.save(state("tn-synth-unknown"));
        DeviceSafetyDecision unknown = policy.evaluate(request("heating", "turn_on", Map.of()));
        assertThat(unknown.allowed()).isFalse();
        assertThat(unknown.reasonCode()).isEqualTo(DeviceSafetyReason.ACTION_CATEGORY_MISMATCH);
    }

    @Test
    void adjustRequiresSyntheticModelsDeclaredParameter() {
        FakeRegistry registry = new FakeRegistry();
        registry.save(state(SyntheticConformanceDeviceCapabilityResolver.MODEL_ID));
        DefaultDeviceSafetyPolicy policy = new DefaultDeviceSafetyPolicy(
                registry,
                List.of(resolver, new DefaultDeviceCapabilityResolver()),
                new SimpleMeterRegistry(),
                Clock.fixed(NOW, ZoneOffset.UTC),
                120,
                600,
                10);

        DeviceSafetyDecision missing = policy.evaluate(request("heating", "adjust", Map.of("target_value", 22)));
        assertThat(missing.allowed()).isFalse();
        assertThat(missing.reasonCode()).isEqualTo(DeviceSafetyReason.ADJUST_PARAMETERS_MISSING);

        assertThat(policy.evaluate(request("heating", "adjust", Map.of("target_temperature", 22))).allowed())
                .isTrue();
    }

    private DeviceSafetyRequest request(String category, String action, Map<String, Object> parameters) {
        return new DeviceSafetyRequest("farm-d4", "device-a", category, action, parameters);
    }

    private DeviceStateRecord state(String modelId) {
        Map<String, Object> attributes = new LinkedHashMap<>();
        attributes.put(SyntheticConformanceDeviceCapabilityResolver.ADAPTER_ATTRIBUTE,
                SyntheticConformanceDeviceCapabilityResolver.ADAPTER_ID);
        attributes.put(SyntheticConformanceDeviceCapabilityResolver.MODEL_ATTRIBUTE, modelId);
        return DeviceStateRecord.builder()
                .farmId("farm-d4")
                .assetId("device-a")
                .deviceType("heater")
                .state("online")
                .reportedAt(NOW)
                .observedAt(NOW)
                .attributes(attributes)
                .build();
    }

    private static final class FakeRegistry implements DeviceStateRegistry {
        private DeviceStateRecord state;

        @Override
        public void save(DeviceStateRecord state) {
            this.state = state;
        }

        @Override
        public Optional<DeviceStateRecord> find(String farmId, String assetId) {
            return Optional.ofNullable(state);
        }

        @Override
        public Map<String, DeviceStateRecord> findAll() {
            return state == null ? Map.of() : Map.of(state.getFarmId() + "/" + state.getAssetId(), state);
        }

        @Override
        public RegistryStatus status() {
            return new RegistryStatus("fake", true, NOW, state == null ? 0 : 1);
        }
    }
}
