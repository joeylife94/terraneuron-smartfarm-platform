package com.terraneuron.sense.service;

import com.terraneuron.sense.model.DeviceSafetyDecision;
import com.terraneuron.sense.model.DeviceSafetyReason;
import com.terraneuron.sense.model.DeviceSafetyRequest;
import com.terraneuron.sense.model.DeviceStateRecord;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DeviceSafetyNullAdjustTest {

    private static final Instant NOW = Instant.parse("2026-07-18T03:00:00Z");

    @Mock
    private DeviceStateRegistry registry;

    @Test
    void nullAdjustValueIsBlockedWithStableReason() {
        DeviceStateRecord state = DeviceStateRecord.builder()
                .farmId("farm-1")
                .assetId("heater-01")
                .deviceType("heater")
                .state("online")
                .maintenanceMode(false)
                .observedAt(NOW)
                .reportedAt(NOW)
                .build();
        when(registry.find("farm-1", "heater-01")).thenReturn(Optional.of(state));
        DefaultDeviceSafetyPolicy policy = new DefaultDeviceSafetyPolicy(
                registry,
                java.util.List.of(new DefaultDeviceCapabilityResolver()),
                new SimpleMeterRegistry(),
                Clock.fixed(NOW, ZoneOffset.UTC),
                120,
                600,
                10);
        Map<String, Object> parameters = new LinkedHashMap<>();
        parameters.put("target_value", null);

        DeviceSafetyDecision decision = policy.evaluate(new DeviceSafetyRequest(
                "farm-1", "heater-01", "heating", "adjust", parameters));

        assertThat(decision.allowed()).isFalse();
        assertThat(decision.reasonCode()).isEqualTo(DeviceSafetyReason.ADJUST_PARAMETERS_MISSING);
    }
}
